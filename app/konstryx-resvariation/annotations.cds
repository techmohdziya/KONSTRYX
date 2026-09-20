using WorkflowService as service from '../../srv/workflow-service';

// Flattened columns are elements of a projection and nothing else names them,
// so without this the filter bar offers "reservationNo" and "projectCode" as
// the labels a coordinator reads.
annotate service.ReservationVariations with {
  docNo         @title : 'Variation';
  status        @title : 'Status';
  reason        @title : 'Reason';
  narrative     @title : 'What changed';
  effectiveFrom @title : 'Effective from';
  decidedBy     @title : 'Decided by';
  decidedOn     @title : 'Decided on';
  deltaAmount   @title : 'Change in value';
  reservationNo @title : 'Reservation';
  projectCode   @title : 'Project';
  verticalType  @title : 'Vertical';
  raisedBy      @title : 'Raised by';
  raisedOn      @title : 'Raised on';
};

annotate service.ReservationVariationLines with {
  variationNo      @title : 'Variation';
  qtyBefore        @title : 'Quantity before';
  qtyAfter         @title : 'Quantity after';
  rateBefore       @title : 'Rate before';
  rateAfter        @title : 'Rate after';
  daysBefore       @title : 'Days before';
  daysAfter        @title : 'Days after';
  encumberedBefore @title : 'Locked before';
  encumberedAfter  @title : 'Locked after';
  delta            @title : 'Change';
};

annotate service.ReservationVariations with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Reservation Variation',
    TypeNamePlural : 'Reservation Variations',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : narrative },
  },

  // What a cost engineer opens this for: which job, what kind of event, and
  // which way the money went. Reason before dates, because "how much of this
  // was rate and how much was duration" is the question a variation account
  // exists to answer.
  UI.SelectionFields : [ projectCode, reason, reservationNo, verticalType ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    // Largest ask first. A variation account is read to find what moved the
    // budget, and the one that moved it most is what moved it.
    SortOrder      : [
      { $Type : 'Common.SortOrderType', Property : deltaAmount, Descending : true },
    ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Variation' },
    { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
    { $Type : 'UI.DataField', Value : reservationNo, Label : 'Reservation' },
    { $Type : 'UI.DataField', Value : reason, Label : 'Reason' },
    { $Type : 'UI.DataField', Value : deltaAmount, Label : 'Change in value',
      Criticality : deltaCriticality },
    { $Type : 'UI.DataField', Value : effectiveFrom, Label : 'Effective from' },
    { $Type : 'UI.DataField', Value : decidedBy, Label : 'Decided by' },
    { $Type : 'UI.DataField', Value : narrative, Label : 'What changed' },
  ],

  UI.FieldGroup #Change : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : docNo, Label : 'Variation' },
      { $Type : 'UI.DataField', Value : reason, Label : 'Reason' },
      { $Type : 'UI.DataField', Value : narrative, Label : 'What changed' },
      { $Type : 'UI.DataField', Value : deltaAmount, Label : 'Change in value',
        Criticality : deltaCriticality },
      { $Type : 'UI.DataField', Value : effectiveFrom, Label : 'Effective from' },
    ],
  },

  UI.FieldGroup #Origin : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
      { $Type : 'UI.DataField', Value : reservationNo, Label : 'Reservation' },
      { $Type : 'UI.DataField', Value : verticalType, Label : 'Vertical' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status' },
      { $Type : 'UI.DataField', Value : decidedBy, Label : 'Decided by' },
      { $Type : 'UI.DataField', Value : decidedOn, Label : 'Decided on' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Change', Label : 'Change',
      Target : '@UI.FieldGroup#Change' },
    { $Type : 'UI.ReferenceFacet', ID : 'Origin', Label : 'Origin',
      Target : '@UI.FieldGroup#Origin' },
    { $Type : 'UI.ReferenceFacet', ID : 'Lines', Label : 'Lines Moved',
      Target : 'lines/@UI.LineItem' },
  ],
);

// Before beside after, in that order, for every figure. The reservation line
// carries only the current one, so this table is the only place the move can
// be read as a move rather than as a result.
annotate service.ReservationVariationLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : qtyBefore, Label : 'Quantity before' },
    { $Type : 'UI.DataField', Value : qtyAfter, Label : 'Quantity after' },
    { $Type : 'UI.DataField', Value : rateBefore, Label : 'Rate before' },
    { $Type : 'UI.DataField', Value : rateAfter, Label : 'Rate after' },
    { $Type : 'UI.DataField', Value : daysBefore, Label : 'Days before' },
    { $Type : 'UI.DataField', Value : daysAfter, Label : 'Days after' },
    { $Type : 'UI.DataField', Value : encumberedBefore, Label : 'Locked before' },
    { $Type : 'UI.DataField', Value : encumberedAfter, Label : 'Locked after' },
    { $Type : 'UI.DataField', Value : delta, Label : 'Change',
      Criticality : deltaCriticality },
  ],
);
