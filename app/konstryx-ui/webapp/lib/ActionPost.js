sap.ui.define([], function () {
	"use strict";

	/**
	 * Posts an OData action as a hand-built request, with the CSRF handshake.
	 *
	 * **Why any of this is hand-built.** A Decimal action parameter cannot go
	 * through the v4 model's typed path at all: SAPUI5 always negotiates
	 * IEEE754Compatible=true and sends Decimals as bare JSON numbers, while
	 * CAP Java's action-parameter deserialiser accepts a Decimal only as a
	 * quoted string under that flag. So every Decimal-carrying action posts
	 * raw (tracker I-36).
	 *
	 * **Why it needs this helper.** Raw posts worked locally and 403'd on every
	 * deployed environment. The approuter enforces CSRF on the /odata route,
	 * the model's own token was never attached to a hand-built request, and the
	 * approuter answers with the plain string "Forbidden" — which the old code
	 * fed straight to JSON.parse, so the user saw
	 * `Unexpected token 'F', "Forbidden" is not valid JSON` rather than
	 * anything about permissions. Nothing local reproduces it: there is no
	 * approuter in front of a developer's service.
	 *
	 * Two rules follow, and both are the point of this module:
	 *
	 *   1. Fetch a CSRF token and send it. Cached per service root, and
	 *      re-fetched once on a 403, because a token expires with the session
	 *      and the retry is invisible to the caller.
	 *   2. Never assume the response is JSON. An error from the approuter or
	 *      the gorouter is plain text, and a parse failure there hides the
	 *      real status behind a syntax error.
	 */

	var mTokens = {};

	/** The service root, which is what the approuter issues a token against. */
	function rootOf(sUrl) {
		var iOData = sUrl.indexOf("/odata/");
		if (iOData < 0) {
			return sUrl;
		}
		// .../odata/v4/<service>/  — four segments past the origin.
		var aParts = sUrl.substring(iOData).split("/");
		return sUrl.substring(0, iOData) + "/" + aParts[1] + "/" + aParts[2] + "/"
			+ aParts[3] + "/";
	}

	function fetchToken(sRoot) {
		if (mTokens[sRoot]) {
			return Promise.resolve(mTokens[sRoot]);
		}
		return fetch(sRoot, {
			method: "HEAD",
			credentials: "same-origin",
			headers: { "x-csrf-token": "Fetch" }
		}).then(function (oResponse) {
			var sToken = oResponse.headers.get("x-csrf-token");
			if (sToken) {
				mTokens[sRoot] = sToken;
			}
			// A missing token is not fatal: a service with CSRF disabled never
			// issues one, and the post below simply goes without.
			return sToken;
		}).catch(function () {
			return null;
		});
	}

	/** The body, whatever the server actually sent. */
	function readBody(oResponse) {
		return oResponse.text().then(function (sText) {
			var oJson = null;
			try {
				oJson = sText ? JSON.parse(sText) : null;
			} catch (e) {
				oJson = null;
			}
			return { json: oJson, text: sText };
		});
	}

	function messageOf(oRead, oResponse, sFallback) {
		if (oRead.json && oRead.json.error && oRead.json.error.message) {
			return oRead.json.error.message;
		}
		if (oRead.text) {
			// Plain text: say what it was AND what the status was, because
			// "Forbidden" alone does not tell anyone it is a CSRF rejection.
			return oResponse.status + " " + oRead.text.substring(0, 200);
		}
		return sFallback;
	}

	function send(sUrl, oBody, sToken) {
		var mHeaders = {
			"Content-Type": "application/json",
			"Accept": "application/json"
		};
		if (sToken) {
			mHeaders["x-csrf-token"] = sToken;
		}
		return fetch(sUrl, {
			method: "POST",
			credentials: "same-origin",
			headers: mHeaders,
			body: JSON.stringify(oBody || {})
		});
	}

	return {
		/**
		 * POST an action and resolve with its response body.
		 *
		 * @param {string} sUrl absolute action URL
		 * @param {object} oBody action parameters, serialised as-is so a
		 *        Decimal stays a bare JSON number
		 * @param {string} [sFallback] message to use when the server says
		 *        nothing useful
		 * @returns {Promise<object>} the parsed body
		 */
		post: function (sUrl, oBody, sFallback) {
			var sRoot = rootOf(sUrl),
				sMessage = sFallback || "The request was refused.";

			return fetchToken(sRoot).then(function (sToken) {
				return send(sUrl, oBody, sToken).then(function (oResponse) {
					if (oResponse.status !== 403) {
						return oResponse;
					}
					// Stale or missing token. Drop it, fetch once more and
					// retry — a session that outlives its token is ordinary,
					// and making the user retry by hand would be theatre.
					delete mTokens[sRoot];
					return fetchToken(sRoot).then(function (sFresh) {
						return sFresh ? send(sUrl, oBody, sFresh) : oResponse;
					});
				});
			}).then(function (oResponse) {
				return readBody(oResponse).then(function (oRead) {
					if (!oResponse.ok) {
						throw new Error(messageOf(oRead, oResponse, sMessage));
					}
					return oRead.json || {};
				});
			});
		}
	};
});
