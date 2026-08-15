sap.ui.define([
	"sap/m/p13n/Engine",
	"sap/m/p13n/SelectionController",
	"sap/m/p13n/SortController",
	"sap/m/p13n/GroupController",
	"sap/m/p13n/FilterController",
	"sap/m/p13n/MetadataHelper",
	"sap/ui/export/Spreadsheet",
	"sap/ui/export/library",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (Engine, SelectionController, SortController, GroupController,
             FilterController, MetadataHelper, Spreadsheet, exportLibrary,
             MessageBox, MessageToast) {
	"use strict";

	var EdmType = exportLibrary.EdmType;

	/**
	 * The list behaviour every screen is expected to have: choose which columns
	 * show and in what order, sort and group by any of them, filter on any
	 * field, save the whole arrangement as a named view, and download it.
	 *
	 * Built once rather than per screen, for the same reason the importer was.
	 * Forty modules each growing their own personalization means forty
	 * behaviours, and the one thing a user needs from a list is that it works
	 * the same way everywhere.
	 *
	 * Views are stored through CollaborationService.UserVariants — the backend
	 * that already enforces one default per table per person, isolation between
	 * users, and administrator-published variants everyone can read but only an
	 * administrator can change. sap.m.VariantManagement is used rather than the
	 * sap.ui.fl one precisely because it is not tied to the Flexibility service:
	 * the variants belong to KONSTRYX's own database, so they deploy, back up
	 * and restore with the rest of the tenant's data.
	 */
	return {

		/**
		 * @param {object} o
		 *   table      the sap.m.Table or sap.ui.table.Table to personalize
		 *   variant    the sap.m.VariantManagement control
		 *   target     stable identifier for this table, e.g. masters.resources
		 *   fields     [{key, label, path, type}] every filterable/sortable field
		 *   model      the OData model name filters are applied against, or null
		 *              when the table is bound to a client-side tree
		 *   onApply    function(state) called after a variant or dialog applies
		 *   controller the owning controller, used to reach the collaboration model
		 */
		attach: function (o) {
			var that = this;
			this._byTarget = this._byTarget || {};
			this._byTarget[o.target] = o;

			var oHelper = new MetadataHelper(o.fields.map(function (f) {
				return { key: f.key, label: f.label, path: f.path || f.key };
			}));

			Engine.getInstance().register(o.table, {
				helper: oHelper,
				controller: {
					Columns: new SelectionController({
						targetAggregation: o.columnAggregation || "columns",
						control: o.table
					}),
					Sorter: new SortController({ control: o.table }),
					Groups: new GroupController({ control: o.table }),
					Filter: new FilterController({ control: o.table })
				}
			});

			Engine.getInstance().attachStateChange(function (oEvent) {
				if (oEvent.getParameter("control") !== o.table) {
					return;
				}
				if (o.onApply) {
					o.onApply(oEvent.getParameter("state"));
				}
				// A change to a saved view is a change the user can keep.
				if (o.variant) {
					o.variant.currentVariantSetModified(true);
				}
			});

			this._loadVariants(o);
			return this;
		},

		/** Opens the personalization dialog on the panels the screen asked for. */
		openSettings: function (oTable, aPanels) {
			Engine.getInstance().show(oTable, aPanels || ["Columns", "Sorter", "Groups", "Filter"]);
		},

		// ------------------------------------------------------------- variants

		_collaborationModel: function (o) {
			return o.controller.getOwnerComponent().getModel("collab")
				|| o.controller.getModel("collab");
		},

		/**
		 * Loads this person's saved views plus anything an administrator
		 * published, and applies their default if they have one.
		 */
		_loadVariants: function (o) {
			var oModel = this._collaborationModel(o);
			if (!oModel || !o.variant) {
				return;
			}
			var that = this;
			var oList = oModel.bindList("/UserVariants", null, null, null, {
				$filter: "target eq '" + o.target + "'",
				$select: "ID,variantName,payload,isDefault,isPublic,user"
			});

			oList.requestContexts(0, 200).then(function (aContexts) {
				o.variant.removeAllItems();
				var oDefault = null;
				aContexts.forEach(function (oContext) {
					var v = oContext.getObject();
					o.variant.addItem(new sap.m.VariantItem({
						key: v.ID,
						title: v.variantName,
						// A published view is everyone's; only an administrator
						// may rename or delete it, which the backend enforces
						// anyway - this just stops the UI offering it.
						remove: !v.isPublic,
						rename: !v.isPublic,
						changeable: !v.isPublic,
						executeOnSelect: false
					}));
					if (v.isDefault) {
						oDefault = v;
					}
				});
				that._variantsByTarget = that._variantsByTarget || {};
				that._variantsByTarget[o.target] = aContexts.map(function (c) { return c.getObject(); });

				if (oDefault) {
					o.variant.setSelectedKey(oDefault.ID);
					that._applyPayload(o, oDefault.payload);
				}
			}).catch(function () {
				// A screen whose saved views cannot be read is still a usable
				// screen, so this is deliberately not an error dialog.
			});
		},

		_applyPayload: function (o, sPayload) {
			if (!sPayload) {
				return;
			}
			var oState;
			try {
				oState = JSON.parse(sPayload);
			} catch (e) {
				return;
			}
			Engine.getInstance().applyState(o.table, oState);
		},

		/** Called from the screen's VariantManagement select event. */
		selectVariant: function (sTarget, sKey) {
			var o = this._byTarget[sTarget],
				aVariants = (this._variantsByTarget || {})[sTarget] || [];
			var oVariant = aVariants.filter(function (v) { return v.ID === sKey; })[0];
			if (o && oVariant) {
				this._applyPayload(o, oVariant.payload);
			}
		},

		/**
		 * Called from the screen's VariantManagement save event.
		 *
		 * "Save" on an existing view overwrites it; "Save As" creates a new one.
		 * The backend owns the rules either way — it refuses a duplicate name,
		 * refuses a non-administrator publishing, and clears the previous
		 * default when a new one is set, so none of that is reimplemented here.
		 */
		saveVariant: function (sTarget, oEvent) {
			var o = this._byTarget[sTarget],
				oModel = this._collaborationModel(o),
				that = this;

			var sName = oEvent.getParameter("name"),
				bDefault = !!oEvent.getParameter("def"),
				bPublic = !!oEvent.getParameter("public"),
				bOverwrite = !!oEvent.getParameter("overwrite"),
				sKey = oEvent.getParameter("key");

			Engine.getInstance().retrieveState(o.table).then(function (oState) {
				var sPayload = JSON.stringify(oState);

				function done() {
					MessageToast.show("View \"" + sName + "\" saved.");
					that._loadVariants(o);
				}

				function failed(oError) {
					MessageBox.error(oError.message || "The view could not be saved.");
				}

				if (bOverwrite && sKey) {
					var oContext = oModel
						.bindContext("/UserVariants(" + sKey + ")", null, { $$updateGroupId: "variant" })
						.getBoundContext();
					oContext.setProperty("payload", sPayload);
					oContext.setProperty("variantName", sName);
					oContext.setProperty("isDefault", bDefault);
					oModel.submitBatch("variant").then(done).catch(failed);
					return;
				}

				oModel.bindList("/UserVariants", null, null, null, { $$updateGroupId: "variant" })
					.create({
						target: sTarget,
						variantName: sName,
						payload: sPayload,
						isDefault: bDefault,
						isPublic: bPublic
					})
					.created()
					.then(done)
					.catch(failed);
				oModel.submitBatch("variant");
			});
		},

		// --------------------------------------------------------------- export

		/**
		 * Excel, through sap.ui.export.Spreadsheet — the same component S/4 list
		 * reports use, so the file opens with real columns and types rather than
		 * a CSV that Excel guesses at.
		 *
		 * The export follows the table as the user has arranged it: the columns
		 * they chose, in their order, with their filters applied.
		 */
		exportToExcel: function (sTarget, aRows, sFileName) {
			var o = this._byTarget[sTarget];
			if (!o) {
				return;
			}

			var aVisible = this._visibleFields(o);
			var aColumns = aVisible.map(function (f) {
				return {
					label: f.label,
					property: f.path || f.key,
					type: f.edm || EdmType.String,
					width: f.width || 18
				};
			});

			new Spreadsheet({
				workbook: { columns: aColumns, hierarchyLevel: o.hierarchyLevel },
				dataSource: aRows,
				fileName: (sFileName || sTarget.replace(/\./g, "-")) + ".xlsx",
				worker: false   // the dev server is same-origin but not cross-origin isolated
			}).build().then(function () {
				MessageToast.show("Downloaded " + aRows.length + " rows.");
			}).catch(function (oError) {
				MessageBox.error("The download failed: " + (oError.message || oError));
			});
		},

		/**
		 * There is no PDF export in SAPUI5, and there is none in an S/4 list
		 * report either — S/4 offers Export to Spreadsheet, and PDF comes from
		 * a form template rendered on the backend. Rather than pretend, this
		 * opens the browser's print dialog against a print stylesheet, which is
		 * how a user gets a PDF of a list today.
		 */
		printView: function () {
			window.print();
		},

		_visibleFields: function (o) {
			var aKeys = (o.table.getColumns() || []).filter(function (c) {
				return c.getVisible();
			}).map(function (c) {
				return c.data && c.data("p13nKey") ? c.data("p13nKey") : null;
			});

			var aFields = o.fields.filter(function (f) {
				return aKeys.indexOf(f.key) > -1;
			});
			return aFields.length ? aFields : o.fields;
		}
	};
});
