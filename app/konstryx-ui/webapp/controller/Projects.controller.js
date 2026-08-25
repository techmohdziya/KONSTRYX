sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ObjectLinks",
	"konstryx/lib/ActionPost",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, ObjectLinks, ActionPost, JSONModel, MessageBox, MessageToast) {
	"use strict";

	/**
	 * The project list, and the two things a person does from it: create one,
	 * and send it to S/4.
	 *
	 * Both were missing until now, which is why the only projects on any tenant
	 * were the seeded ones. A product whose projects can only arrive in a
	 * content pack is a demo, not a product.
	 */
	return BaseController.extend("konstryx.controller.Projects", {

		onInit: function () {
			this.getRouter().getRoute("projects").attachPatternMatched(function () {
				this.setNavKey("projects");
				var oBinding = this.byId("projectTable").getBinding("items");
				if (oBinding) {
					oBinding.attachEventOnce("dataReceived", function () {
						this.byId("projectCount").setText(
							"Projects (" + oBinding.getLength() + ")");
					}, this);
				}
			}, this);
		},

		onProjectLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("pj").getObject();
			ObjectLinks.open(this, "project", oRow, oEvent.getSource());
		},

		// ------------------------------------------------------------- create

		onNewProject: function () {
			var that = this;
			this._resetNewProject();
			if (this._pNewProject) {
				this._pNewProject.then(function (oDialog) { oDialog.open(); });
				return;
			}
			this._pNewProject = this.loadFragment({ name: "konstryx.view.NewProject" })
				.then(function (oDialog) {
					that.getView().addDependent(oDialog);
					oDialog.open();
					return oDialog;
				});
		},

		/**
		 * A fresh form every time, with one empty WBS row already there. The row
		 * is not decoration: a project with no WBS element cannot be released,
		 * so the form should look like one is expected rather than let someone
		 * discover it afterwards.
		 */
		_resetNewProject: function () {
			this.getView().setModel(new JSONModel({
				code: "",
				name: "",
				companyCode: "",
				startDate: "",
				endDate: "",
				contractValue: null,
				wbs: [{ code: "", description: "" }]
			}), "new");
		},

		onAddWbsRow: function () {
			var oModel = this.getView().getModel("new"),
				aWbs = oModel.getProperty("/wbs");
			aWbs.push({ code: "", description: "" });
			oModel.setProperty("/wbs", aWbs);
		},

		onRemoveWbsRow: function (oEvent) {
			var oModel = this.getView().getModel("new"),
				aWbs = oModel.getProperty("/wbs"),
				sPath = oEvent.getSource().getBindingContext("new").getPath(),
				iIndex = parseInt(sPath.split("/").pop(), 10);
			aWbs.splice(iIndex, 1);
			if (aWbs.length === 0) {
				aWbs.push({ code: "", description: "" });
			}
			oModel.setProperty("/wbs", aWbs);
		},

		onCancelNewProject: function () {
			this.byId("newProjectDialog").close();
		},

		onCreateProject: function () {
			var that = this,
				oData = this.getView().getModel("new").getData(),
				aWbs = (oData.wbs || []).filter(function (oRow) {
					return oRow.code && oRow.code.trim();
				});

			// Checked here as well as on the server. The server is the one that
			// decides; this is only so the answer arrives before the round trip.
			if (!oData.code || !oData.name || !oData.companyCode) {
				MessageBox.warning("A project needs a code, a name and a company.");
				return;
			}
			if (aWbs.length === 0) {
				MessageBox.warning("Add at least one WBS element. A project with none "
					+ "cannot be released to S/4, and nothing can be costed against it.");
				return;
			}

			var oButton = this.byId("npCreate");
			oButton.setEnabled(false);
			ActionPost.post("/odata/v4/project/createProject", {
				code: oData.code.trim(),
				name: oData.name.trim(),
				companyCode: oData.companyCode,
				startDate: oData.startDate || null,
				endDate: oData.endDate || null,
				// A bare JSON number, which is why this posts through ActionPost
				// rather than the typed model - see lib/ActionPost (I-36).
				contractValue: oData.contractValue === null || oData.contractValue === ""
					? null : Number(oData.contractValue),
				wbs: aWbs.map(function (oRow) {
					return {
						code: oRow.code.trim(),
						description: (oRow.description || "").trim()
					};
				})
			}, "The project could not be created.").then(function (oBody) {
				that.byId("newProjectDialog").close();
				MessageToast.show(String(oBody.value || "Project created."));
				that._refresh();
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The project could not be created.");
			}).finally(function () {
				oButton.setEnabled(true);
			});
		},

		// ----------------------------------------------------- org from S/4

		/**
		 * Re-reads the organizational values from the connected S/4.
		 *
		 * Read-only against S/4 and safe to repeat: it writes only the local
		 * mirror and the company org fields, and it leaves a value S/4 recognises
		 * exactly as it is. The report is shown in full rather than summarised,
		 * because the useful half is what it could *not* decide - an API that
		 * answered 403, a company with no S/4 code, a plant that needs a choice.
		 */
		onSyncOrg: function () {
			var that = this,
				oButton = this.byId("syncOrgButton");

			oButton.setEnabled(false);
			ActionPost.post("/odata/v4/admin/syncOrgFromS4", {},
					"The organizational values could not be read.").then(function (oBody) {
				MessageBox.information(String(oBody.value || ""), {
					title: "Organizational values from S/4",
					contentWidth: "40rem"
				});
				that._refresh();
			}).catch(function (oError) {
				MessageBox.error(oError.message
					|| "The organizational values could not be read.");
			}).finally(function () {
				oButton.setEnabled(true);
			});
		},

		// ------------------------------------------------------------ release

		/**
		 * Release now posts to S/4 rather than only queueing, so this asks
		 * first. It creates an Enterprise Project and its WBS elements in the
		 * connected system, and that is not undone by clicking again.
		 */
		onReleaseToS4: function (oEvent) {
			var that = this,
				oContext = oEvent.getSource().getBindingContext("pj"),
				oProject = oContext.getObject();

			MessageBox.confirm(
				"Send " + oProject.code + " to S/4?\n\n"
					+ "This creates the project and its WBS elements in the connected "
					+ "S/4 system. It is not undone by releasing again.",
				{
					title: "Release to S/4",
					emphasizedAction: MessageBox.Action.OK,
					onClose: function (sAction) {
						if (sAction === MessageBox.Action.OK) {
							that._release(oContext, oProject.code);
						}
					}
				});
		},

		_release: function (oContext, sCode) {
			var that = this,
				oOperation = this.getModel("pj").bindContext(
					"ProjectService.releaseToS4(...)", oContext);

			oOperation.execute().then(function () {
				var vResult = oOperation.getBoundContext().getValue();
				MessageBox.information(
					String(vResult && vResult.value !== undefined ? vResult.value : vResult),
					{ title: sCode });
				that._refresh();
			}).catch(function (oError) {
				// Say what S/4 said. A refusal names a field or an org value,
				// and that is the whole of the diagnosis.
				MessageBox.error(oError.message || "S/4 refused the project.");
				that._refresh();
			});
		},

		_refresh: function () {
			var oBinding = this.byId("projectTable").getBinding("items");
			if (oBinding) {
				oBinding.refresh();
			}
		}
	});
});
