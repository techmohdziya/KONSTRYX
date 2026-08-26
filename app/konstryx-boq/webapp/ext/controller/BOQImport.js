sap.ui.define([
    "sap/m/Dialog",
    "sap/m/Button",
    "sap/m/VBox",
    "sap/m/Text",
    "sap/m/CheckBox",
    "sap/ui/unified/FileUploader",
    "sap/m/MessageBox",
    "sap/m/MessageToast",
    "sap/m/BusyDialog"
], function (Dialog, Button, VBox, Text, CheckBox, FileUploader, MessageBox, MessageToast, BusyDialog) {
    "use strict";

    // A bill arrives from the quantity surveyor as a spreadsheet, every time.
    // The import engine has always been there; what was missing was any way to
    // hand it a file. Fiori Elements renders an action's parameters as form
    // fields, so a LargeString parameter becomes a text box - which is asking
    // someone to paste six hundred lines of CSV, not to upload a bill.
    //
    // The file is read in the browser and passed to the same importItems
    // action the tests exercise. Nothing about the engine changes; this is the
    // file picker it never had.

    var REQUIRED = ["itemNo", "qty", "rate"];
    var KNOWN = ["itemNo", "code", "description", "qty", "uom", "rate"];

    /**
     * Checks the header before anything is sent.
     *
     * The server rejects a bad header too, but it can only do so after the
     * whole file has crossed the wire, and its message names the columns it
     * wanted rather than the ones the file has. Reading the first line here
     * lets the dialog say what is wrong with the file in front of the person
     * who chose it.
     */
    function inspectHeader(text) {
        var firstLine = (text.split(/\r?\n/)[0] || "").trim();
        if (!firstLine) {
            return { ok: false, reason: "The file is empty." };
        }
        // Semicolons, because that is what the parser on the other side reads.
        // Accepting commas here would let the dialog report a healthy set of
        // columns for a file the server then rejects as having none of them,
        // and a comma-separated export is the commonest way a bill arrives
        // wrong.
        if (firstLine.indexOf(";") === -1 && firstLine.indexOf(",") > -1) {
            return {
                ok: false,
                reason: "This file is comma-separated. A bill has to use " +
                    "semicolons, because a description routinely contains a " +
                    "comma and would be split into two columns."
            };
        }
        var columns = firstLine.split(";").map(function (c) {
            return c.trim().replace(/^"|"$/g, "");
        });
        var missing = REQUIRED.filter(function (name) {
            return columns.indexOf(name) === -1;
        });
        if (missing.length) {
            return {
                ok: false,
                reason: "The file is missing " + missing.join(" and ") +
                    ". Its columns are: " + columns.join(", ") + "."
            };
        }
        var unknown = columns.filter(function (name) {
            return name && KNOWN.indexOf(name) === -1;
        });
        return {
            ok: true,
            columns: columns,
            // Not an error. A QS spreadsheet routinely carries columns the
            // bill does not need, and silently dropping them without saying so
            // is how someone discovers at handover that a column they cared
            // about was never read.
            ignored: unknown
        };
    }

    function rowCount(text) {
        return text.split(/\r?\n/).filter(function (l) { return l.trim(); }).length - 1;
    }

    return {
        /**
         * Entry point for the manifest-declared header action.
         *
         * `this` is not a controller here - Fiori Elements binds its own
         * extension API - so nothing is read off it. Different versions hand
         * the handler either the press event or the bound context directly,
         * and both shapes are accepted rather than pinning this file to one
         * runtime.
         *
         * It returns a promise that settles when the dialog closes. Fiori
         * Elements holds a busy lock across a custom action and releases it on
         * the returned promise; returning nothing leaves the lock held, the
         * page covered by a busy overlay, and the dialog underneath it - which
         * looks exactly like a button that does nothing until the lock times
         * out thirty seconds later.
         */
        openUpload: function (arg) {
            var context = null;
            var owner = null;

            if (arg && typeof arg.getSource === "function") {
                owner = arg.getSource();
                context = owner.getBindingContext();
            } else if (arg && typeof arg.getObject === "function") {
                context = arg;
            } else if (this && typeof this.getBindingContext === "function") {
                context = this.getBindingContext();
            }

            if (!context) {
                MessageBox.error("Open a bill of quantities first.");
                return Promise.resolve();
            }
            var model = context.getModel();
            var closed;
            var settle = new Promise(function (resolve) { closed = resolve; });

            var summary = new Text({ text: "Choose a CSV exported from the bill." });
            var validateOnly = new CheckBox({
                text: "Check the file without importing",
                selected: false
            });
            var fileContent = null;

            var uploader = new FileUploader({
                name: "boq",
                fileType: ["csv", "txt"],
                placeholder: "No file chosen",
                width: "100%",
                change: function (e) {
                    var file = e.getParameter("files") && e.getParameter("files")[0];
                    fileContent = null;
                    if (!file) {
                        summary.setText("Choose a CSV exported from the bill.");
                        return;
                    }
                    var reader = new FileReader();
                    reader.onload = function (loaded) {
                        var text = loaded.target.result;
                        var check = inspectHeader(text);
                        if (!check.ok) {
                            summary.setText(check.reason);
                            return;
                        }
                        fileContent = text;
                        var note = rowCount(text) + " line(s), columns " +
                            check.columns.join(", ") + ".";
                        if (check.ignored.length) {
                            note += " " + check.ignored.join(", ") +
                                (check.ignored.length === 1 ? " is" : " are") +
                                " not part of a bill and will be ignored.";
                        }
                        summary.setText(note);
                    };
                    reader.onerror = function () {
                        summary.setText("That file could not be read.");
                    };
                    reader.readAsText(file);
                }
            });

            var dialog = new Dialog({
                title: "Import bill items",
                contentWidth: "34rem",
                content: [new VBox({
                    items: [uploader, validateOnly, summary]
                }).addStyleClass("sapUiSmallMargin")],
                beginButton: new Button({
                    text: "Import",
                    type: "Emphasized",
                    press: function () {
                        if (!fileContent) {
                            MessageBox.error("Choose a file that has the columns a bill needs.");
                            return;
                        }
                        var busy = new BusyDialog({ text: "Reading the bill..." });
                        busy.open();
                        var action = model.bindContext(
                            "ProjectService.importItems(...)", context);
                        action.setParameter("fileName", uploader.getValue());
                        action.setParameter("content", fileContent);
                        action.setParameter("validateOnly", validateOnly.getSelected());
                        action.execute().then(function () {
                            busy.close();
                            dialog.close();
                            var outcome = action.getBoundContext().getObject();
                            MessageBox.information(
                                (outcome && outcome.value) || "The bill was imported.");
                            // The header value and the item list both move, so
                            // the page is re-read rather than left showing the
                            // bill as it was before the file arrived.
                            context.refresh();
                        }).catch(function (error) {
                            busy.close();
                            MessageBox.error(
                                (error && error.message) || "The import failed.");
                        });
                    }
                }),
                endButton: new Button({
                    text: "Cancel",
                    press: function () { dialog.close(); }
                }),
                afterClose: function () {
                    dialog.destroy();
                    closed();
                }
            });

            // Attached to the button that opened it when there is one, so the
            // dialog inherits its models and is destroyed with the page. It
            // opens standalone otherwise rather than refusing to open at all.
            if (owner && typeof owner.addDependent === "function") {
                owner.addDependent(dialog);
            }
            dialog.setModel(model);
            dialog.open();
            return settle;
        }
    };
});
