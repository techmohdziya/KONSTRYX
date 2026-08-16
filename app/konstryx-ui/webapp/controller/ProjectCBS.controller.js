sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ObjectLinks",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator"
], function (BaseController, ObjectLinks, Filter, FilterOperator) {
	"use strict";

	/**
	 * The ASSIGNED CBS node of one project — the transactional view, not the
	 * master. From a bill line the CBS code lands here: this node in this
	 * project, the recipe resources keyed to its library leaf, and the bill
	 * lines it carries. The library remains reachable as a secondary link
	 * target for whoever maintains it, but a transaction never navigates a
	 * user into master maintenance by default.
	 */
	return BaseController.extend("konstryx.controller.ProjectCBS", {

		onInit: function () {
			this.getRouter().getRoute("projectCBS").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			this.setNavKey("projects");
			var sCbsId = oEvent.getParameter("arguments").cbsId;
			var that = this;

			this.getModel("pj").bindList("/CBS", null, null, null, {
				$filter: "ID eq " + sCbsId,
				$select: "ID,code,level,budgetAmount,libraryNode_ID",
				$expand: "project($select=code,name),libraryNode($select=code,phase)"
			}).requestContexts(0, 1).then(function (aContexts) {
				if (!aContexts.length) {
					that.byId("cbsNodeTitle").setText("CBS node not found");
					return;
				}
				var oNode = aContexts[0].getObject();
				that.byId("cbsNodeTitle").setText(
					oNode.project.code + " · CBS " + oNode.code
					+ (oNode.libraryNode ? " — " + (oNode.libraryNode.phase || "") : ""));
				that.byId("cbsNodeSubtitle").setText(oNode.project.name
					+ " — carries " + Number(oNode.budgetAmount || 0)
						.toLocaleString("en-US", { maximumFractionDigits: 0 })
					+ (oNode.libraryNode_ID
						? "" : " · no library origin, so no recipe can attach"));

				["recipeTable", "prodTable"].forEach(function (sId) {
					var oBinding = that.byId(sId).getBinding("items");
					oBinding.filter(oNode.libraryNode_ID
						? [new Filter("linkedCBS_ID", FilterOperator.EQ, oNode.libraryNode_ID)]
						: [new Filter("linkedCBS_ID", FilterOperator.EQ,
							"00000000-0000-0000-0000-000000000000")]);
					if (oBinding.isSuspended()) {
						oBinding.resume();
					}
				});
				var oMapped = that.byId("mappedTable").getBinding("items");
				oMapped.filter([new Filter("cbs_ID", FilterOperator.EQ, oNode.ID)]);
				if (oMapped.isSuspended()) {
					oMapped.resume();
				}
			});
		},

		onResourceLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("md").getObject();
			ObjectLinks.open(this, "resource",
				oRow.resource || oRow.material || {}, oEvent.getSource());
		}
	});
});
