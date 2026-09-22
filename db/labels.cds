/**
 * Field labels for the whole model.
 *
 * Every filter bar, column list and Adapt Filters dialog reads these. Without
 * them a user is offered the CDS element name, which is how a project manager
 * came to be asked to filter on estTotal, cumDoneQty and s4GIDoc.
 *
 * They live here rather than on each entity so the model files stay readable,
 * and here rather than in each app so that twelve apps cannot drift apart.
 *
 * Generated, then reviewed. An entry that reads badly is corrected in the
 * generator's dictionary rather than here, so a regeneration keeps the fix.
 */
using { konstryx.admin } from './admin';
using { konstryx.apr } from './apr';
using { konstryx.auth } from './auth';
using { konstryx.bud } from './bud';
using { konstryx.eq } from './eq';
using { konstryx.fin } from './fin';
using { konstryx.ins } from './ins';
using { konstryx.int } from './int';
using { konstryx.master } from './master';
using { konstryx.mat } from './mat';
using { konstryx.mpr } from './mpr';
using { konstryx.nr } from './nr';
using { konstryx.prj } from './prj';
using { konstryx.scr } from './scr';
using { konstryx.sf } from './sf';
using { konstryx.sys } from './sys';
using { konstryx.wf } from './wf';

annotate konstryx.admin.CompanyGroup with {
  code              @title : 'Code';
  name              @title : 'Name';
  iasGroup          @title : 'IAS group';
  reportingCcy      @title : 'Reporting currency';
  reportingRateType @title : 'Reporting rate type';
  companies         @title : 'Companies';
}

annotate konstryx.admin.Company with {
  code           @title : 'Code';
  legalName      @title : 'Legal name';
  group          @title : 'Group';
  s4CoCode       @title : 'ERP company code';
  defaultPlant   @title : 'Default plant';
  purchOrg       @title : 'Purchasing organisation';
  purchGroup     @title : 'Purchasing group';
  salesOrg       @title : 'Sales organisation';
  profitCtr      @title : 'Profit centre';
  costCtr        @title : 'Cost centre';
  projectProfile @title : 'Project profile';
  ccy            @title : 'Currency';
  isDefault      @title : 'Default';
}

annotate konstryx.admin.S4OrgValue with {
  kind       @title : 'Kind';
  code       @title : 'Code';
  name       @title : 'Name';
  parentCode @title : 'Parent code';
  ccy        @title : 'Currency';
  source     @title : 'Source';
  inUse      @title : 'In use';
  s4System   @title : 'ERP system';
  readAt     @title : 'Read at';
}

annotate konstryx.admin.RoleCollectionMap with {
  persona        @title : 'Persona';
  roleCollection @title : 'Role collection';
  moduleAccess   @title : 'Module access';
}

annotate konstryx.admin.UserCompanyAccess with {
  user      @title : 'User';
  company   @title : 'Company';
  role      @title : 'Role';
  validFrom @title : 'Valid from';
  validTo   @title : 'Valid to';
}

annotate konstryx.admin.PromotionRequest with {
  objectType    @title : 'Object type';
  objectKey     @title : 'Object key';
  currentScope  @title : 'Current scope';
  proposedScope @title : 'Proposed scope';
  requester     @title : 'Requester';
  decision      @title : 'Decision';
  decidedBy     @title : 'Decided by';
  comment       @title : 'Comment';
  status        @title : 'Status';
  age           @title : 'Age';
}

annotate konstryx.admin.S4SyncConfig with {
  company    @title : 'Company';
  objectType @title : 'Object type';
  direction  @title : 'Direction';
  trigger    @title : 'Trigger';
  service    @title : 'Service';
  active     @title : 'Active';
}

annotate konstryx.apr.ApprovalScheme with {
  code       @title : 'Code';
  name       @title : 'Name';
  authObject @title : 'Authorisation object';
  company    @title : 'Company';
  isActive   @title : 'Active';
  validFrom  @title : 'Valid from';
  validTo    @title : 'Valid to';
  steps      @title : 'Steps';
}

annotate konstryx.apr.ApprovalStepDef with {
  scheme        @title : 'Scheme';
  stepNo        @title : 'Step number';
  name          @title : 'Name';
  approver      @title : 'Approver';
  mode          @title : 'Mode';
  minAmount     @title : 'Minimum amount';
  maxAmount     @title : 'Maximum amount';
  ccy           @title : 'Currency';
  isMandatory   @title : 'Mandatory';
  allowChaining @title : 'Allow chaining';
}

annotate konstryx.apr.ApprovalInstance with {
  scheme      @title : 'Scheme';
  entityName  @title : 'Entity name';
  objectID    @title : 'Object';
  objectDocNo @title : 'Document number';
  amount      @title : 'Amount';
  ccy         @title : 'Currency';
  status      @title : 'Status';
  startedAt   @title : 'Started at';
  completedAt @title : 'Completed at';
  steps       @title : 'Steps';
}

annotate konstryx.apr.ApprovalStepInstance with {
  instance    @title : 'Instance';
  stepDef     @title : 'Step definition';
  stepNo      @title : 'Step number';
  name        @title : 'Name';
  actedBy     @title : 'Acted by';
  decision    @title : 'Decision';
  decidedAt   @title : 'Decided at';
  comment     @title : 'Comment';
  delegatedTo @title : 'Delegated to';
}

annotate konstryx.auth.Module with {
  code     @title : 'Code';
  name     @title : 'Name';
  sequence @title : 'Sequence';
  objects  @title : 'Objects';
}

annotate konstryx.auth.AuthObject with {
  code          @title : 'Code';
  name          @title : 'Name';
  module        @title : 'Module';
  entityName    @title : 'Entity name';
  projectScoped @title : 'Project scoped';
  projectPath   @title : 'Project path';
  companyPath   @title : 'Company path';
  activities    @title : 'Activities';
}

annotate konstryx.auth.Activity with {
  code @title : 'Code';
}

annotate konstryx.auth.AuthObjectActivity with {
  authObject @title : 'Authorisation object';
  activity   @title : 'Activity';
}

annotate konstryx.auth.Persona with {
  code        @title : 'Code';
  name        @title : 'Name';
  description @title : 'Description';
  isActive    @title : 'Active';
  isDelivered @title : 'Delivered';
  permissions @title : 'Permissions';
}

annotate konstryx.auth.PersonaPermission with {
  persona    @title : 'Persona';
  authObject @title : 'Authorisation object';
  activity   @title : 'Activity';
  granted    @title : 'Granted';
}

annotate konstryx.auth.UserAssignment with {
  user      @title : 'User';
  persona   @title : 'Persona';
  company   @title : 'Company';
  project   @title : 'Project';
  validFrom @title : 'Valid from';
  validTo   @title : 'Valid to';
  isActive  @title : 'Active';
}

annotate konstryx.bud.Budget with {
  version     @title : 'Version';
  daysToLock  @title : 'Days to lock';
  totalAmount @title : 'Total';
  lines       @title : 'Lines';
  approvals   @title : 'Approvals';
}

annotate konstryx.bud.BudgetLine with {
  budget     @title : 'Budget';
  cbs        @title : 'CBS';
  boqItem    @title : 'BOQ item';
  category   @title : 'Category';
  amount     @title : 'Amount';
  authorised @title : 'Authorised';
  committed  @title : 'Committed';
  encumbered @title : 'Encumbered';
  actual     @title : 'Actual';
  available  @title : 'Available';
  availPct   @title : 'Available %';
  usedPct    @title : 'Used %';
  eac        @title : 'EAC';
  eacMargin  @title : 'EAC margin';
  costRate   @title : 'Cost rate';
  costDelta  @title : 'Cost delta';
}

annotate konstryx.bud.BudgetLedgerEntry with {
  budget    @title : 'Budget';
  line      @title : 'Line';
  category  @title : 'Category';
  amount    @title : 'Amount';
  reference @title : 'Reference';
  reason    @title : 'Reason';
  pairKey   @title : 'Pair key';
}

annotate konstryx.bud.MobilizationAuth with {
  amount     @title : 'Amount';
  validTo    @title : 'Valid to';
  approvedBy @title : 'Approved by';
  approvedOn @title : 'Approved on';
  spend      @title : 'Spend';
}

annotate konstryx.bud.PreBaselineSpend with {
  project   @title : 'Project';
  ma        @title : 'Mobilisation authorisation';
  amount    @title : 'Amount';
  spendDate @title : 'Spend date';
  doc       @title : 'Document';
}

annotate konstryx.bud.BudgetApproval with {
  budget       @title : 'Budget';
  step         @title : 'Step';
  approverRole @title : 'Approver role';
  approvedBy   @title : 'Approved by';
  approvedOn   @title : 'Approved on';
  decision     @title : 'Decision';
  comment      @title : 'Comment';
}

annotate konstryx.bud.AvailabilityLog with {
  budget        @title : 'Budget';
  line          @title : 'Line';
  checkedAmount @title : 'Checked amount';
  result        @title : 'Result';
  checkedOn     @title : 'Checked on';
  sourceDoc     @title : 'Source document';
}

annotate konstryx.eq.EquipmentRequestLine with {
  line         @title : 'Line';
  instances    @title : 'Instances';
  durationDays @title : 'Duration (days)';
  mobDate      @title : 'Mobilisation date';
  demobDate    @title : 'Demobilisation date';
  sourceType   @title : 'Source type';
  sourceDetail @title : 'Source detail';
  vendor       @title : 'Vendor';
  operatorsReq @title : 'Operators required';
}

annotate konstryx.fin.ExchangeRate with {
  fromCcy   @title : 'From';
  toCcy     @title : 'To';
  rateType  @title : 'Rate type';
  validFrom @title : 'Valid from';
  rate      @title : 'Rate';
  source    @title : 'Source';
}

annotate konstryx.fin.FiscalCalendar with {
  code         @title : 'Code';
  name         @title : 'Name';
  company      @title : 'Company';
  variant      @title : 'Variant';
  startMonth   @title : 'Start month';
  weekStartsOn @title : 'Week starts on';
  isDefault    @title : 'Default';
  periods      @title : 'Periods';
}

annotate konstryx.fin.FiscalPeriod with {
  calendar     @title : 'Calendar';
  fiscalYear   @title : 'Fiscal year';
  periodNo     @title : 'Period number';
  name         @title : 'Name';
  startDate    @title : 'Start date';
  endDate      @title : 'End date';
  status       @title : 'Status';
  isAdjustment @title : 'Adjustment period';
}

annotate konstryx.ins.ProjectPeriodReport with {
  project             @title : 'Project';
  period              @title : 'Period';
  periodName          @title : 'Period';
  takenAt             @title : 'Measured at';
  contractValue       @title : 'Contract value';
  variations          @title : 'Variations';
  adjustedValue       @title : 'Adjusted value';
  plannedValue        @title : 'Planned value';
  earnedValue         @title : 'Earned value';
  actualCost          @title : 'Actual cost';
  costVariance        @title : 'Cost variance';
  scheduleVariance    @title : 'Schedule variance';
  cpi                 @title : 'CPI (earned / spent)';
  spi                 @title : 'SPI (earned / planned)';
  costToDate          @title : 'Cost to date';
  signedLabourCost    @title : 'Signed labour cost';
  stockIssuedCost     @title : 'Stock issued cost';
  costToComplete      @title : 'Estimated cost to complete';
  forecastCost        @title : 'Forecast cost';
  forecastMargin      @title : 'Forecast margin';
  forecastMarginPct   @title : 'Forecast margin %';
  percentComplete     @title : 'Percent complete';
  companyCcy          @title : 'Company currency';
  groupCcy            @title : 'Group currency';
  rateType            @title : 'Rate type';
  rateApplied         @title : 'Rate applied';
  adjustedValueGroup  @title : 'Adjusted value (group)';
  forecastCostGroup   @title : 'Forecast cost (group)';
  forecastMarginGroup @title : 'Forecast margin (group)';
  note                @title : 'Note';
}

annotate konstryx.int.SyncRun with {
  config         @title : 'Configuration';
  startedAt      @title : 'Started at';
  finishedAt     @title : 'Finished at';
  direction      @title : 'Direction';
  recordsRead    @title : 'Records read';
  recordsWritten @title : 'Records written';
  result         @title : 'Result';
  errors         @title : 'Errors';
}

annotate konstryx.int.ErrorQueueItem with {
  syncRun    @title : 'Sync run';
  objectType @title : 'Object type';
  objectKey  @title : 'Object key';
  payload    @title : 'Payload';
  error      @title : 'Error';
  attempts   @title : 'Attempts';
  status     @title : 'Status';
}

annotate konstryx.int.S4DocXref with {
  konstryxDoc @title : 'KONSTRYX document';
  s4DocType   @title : 'ERP document type';
  s4DocNo     @title : 'ERP document number';
  s4System    @title : 'ERP system';
}

annotate konstryx.master.ResourceNode with {
  code             @title : 'Code';
  level            @title : 'Level';
  parent           @title : 'Parent';
  verticalType     @title : 'Vertical type';
  description      @title : 'Description';
  consUoM          @title : 'Consumption UoM';
  outputUoM        @title : 'Output UoM';
  s4Material       @title : 'ERP material';
  s4ServiceProduct @title : 'ERP service product';
  defaultCBS       @title : 'Default CBS';
  linkedRate       @title : 'Linked rate';
  children         @title : 'Children';
}

annotate konstryx.master.CBSNode with {
  code             @title : 'Code';
  level            @title : 'Level';
  parent           @title : 'Parent';
  constructionType @title : 'Construction type';
  phase            @title : 'Phase';
  costNature       @title : 'Cost nature';
  allocBasis       @title : 'Allocation basis';
  children         @title : 'Children';
}

annotate konstryx.master.ProjectTemplate with {
  code             @title : 'Code';
  name             @title : 'Name';
  constructionType @title : 'Construction type';
  version          @title : 'Version';
  cbsRoot          @title : 'CBS root';
  resources        @title : 'Resources';
}

annotate konstryx.master.ProjectTemplateResource with {
  template @title : 'Template';
  resource @title : 'Resource';
}

annotate konstryx.master.ProductivityRate with {
  resource          @title : 'Resource';
  linkedCBS         @title : 'Linked CBS';
  activity          @title : 'Activity';
  crewComposition   @title : 'Crew composition';
  outputPerHr       @title : 'Output per hour';
  outputPerManday8h @title : 'Output per man-day (8h)';
  outputUoM         @title : 'Output UoM';
  basis             @title : 'Basis';
  effectiveFrom     @title : 'Effective from';
}

annotate konstryx.master.ConsumptionRate with {
  material            @title : 'Material';
  linkedCBS           @title : 'Linked CBS';
  activity            @title : 'Activity';
  consRate            @title : 'Consumption rate';
  consUoM             @title : 'Consumption UoM';
  wastageAllowancePct @title : 'Wastage allowance %';
  netRate             @title : 'Net rate';
  basis               @title : 'Basis';
  effectiveFrom       @title : 'Effective from';
}

annotate konstryx.master.RateMaster with {
  resource         @title : 'Resource';
  source           @title : 'Source';
  vendor           @title : 'Vendor';
  s4ActivityType   @title : 'ERP activity type';
  s4ServiceProduct @title : 'ERP service product';
  rateValue        @title : 'Rate';
  basis            @title : 'Basis';
  ccy              @title : 'Currency';
  netRate          @title : 'Net rate';
  effectiveFrom    @title : 'Effective from';
  company          @title : 'Company';
}

annotate konstryx.master.Vendor with {
  bpNumber     @title : 'BP number';
  name         @title : 'Name';
  purchOrgs    @title : 'Purchasing organisations';
  paymentTerms @title : 'Payment terms';
  hseCert      @title : 'HSE certificate';
  status       @title : 'Status';
}

annotate konstryx.master.Material with {
  materialCode  @title : 'Material code';
  description   @title : 'Description';
  baseUoM       @title : 'Base UoM';
  materialGroup @title : 'Material group';
}

annotate konstryx.master.WorkforceCatalog with {
  code @title : 'Code';
}

annotate konstryx.master.TradeCatalogue with {
  code         @title : 'Trade';
  description  @title : 'Description';
  discipline   @title : 'Discipline';
  grades       @title : 'Grades';
  certificates @title : 'Certificates required';
}

annotate konstryx.master.TradeGrade with {
  code        @title : 'Grade';
  description @title : 'Description';
  sequence    @title : 'Order';
}

annotate konstryx.master.TradeCertificate with {
  code        @title : 'Certificate';
  description @title : 'Description';
  blocking    @title : 'Stops him working';
}

annotate konstryx.master.ShiftPattern with {
  code          @title : 'Pattern';
  description   @title : 'Description';
  dutyHours     @title : 'Duty day (hours)';
  mandayHours   @title : 'Manday (hours)';
  breakMinutes  @title : 'Break (minutes)';
  allHoursAreOT @title : 'Whole day is overtime';
  calendar      @title : 'Holiday calendar';
  effectiveFrom @title : 'Effective from';
  overtimeSteps @title : 'Overtime ladder';
}

annotate konstryx.master.OvertimeStep with {
  kind         @title : 'Rung';
  description  @title : 'Description';
  costFactor   @title : 'Cost factor';
  chargeFactor @title : 'Charge factor';
  fromHour     @title : 'From hour';
  sequence     @title : 'Order';
}

annotate konstryx.master.HolidayCalendar with {
  code        @title : 'Calendar';
  description @title : 'Description';
  country     @title : 'Country';
  region      @title : 'Region';
  year        @title : 'Year';
  entries     @title : 'Days';
}

annotate konstryx.master.HolidayCalendarEntry with {
  holidayDate @title : 'Date';
  description @title : 'Occasion';
  class       @title : 'Class';
  status      @title : 'Status';
  otKind      @title : 'Overtime rung';
  nonWorking  @title : 'Non-working';
}

annotate konstryx.master.Employee with {
  empNo        @title : 'Works number';
  fullName     @title : 'Name';
  passportNo   @title : 'Passport';
  emiratesId   @title : 'Emirates ID';
  nationality  @title : 'Nationality';
  source       @title : 'Mastered in';
  trade        @title : 'Trade';
  grade        @title : 'Grade';
  shiftPattern @title : 'Shift pattern';
  calendar     @title : 'Holiday calendar';
  costCentre   @title : 'Cost centre';
  gradingBand  @title : 'Grading band';
  joinedOn     @title : 'Joined';
  leftOn       @title : 'Left';
  status       @title : 'Status';
  documents    @title : 'Documents';
}

annotate konstryx.master.EmployeeDocument with {
  code        @title : 'Document';
  description @title : 'Description';
  documentNo  @title : 'Number';
  issuedOn    @title : 'Issued';
  expiresOn   @title : 'Expires';
  blocking    @title : 'Stops him working';
}

annotate konstryx.master.CrewTemplate with {
  code                  @title : 'Crew';
  description           @title : 'Description';
  outputBasis           @title : 'Output stated per';
  outputPerDay          @title : 'Output per day';
  outputUoM             @title : 'Unit';
  minimumManning        @title : 'Minimum manning';
  substitutionAllowed   @title : 'Substitution allowed';
  foremanCountsToOutput @title : 'Foreman counts to output';
  mixedSourcingAllowed  @title : 'Mixed sourcing allowed';
  crewRatePerHr         @title : 'Crew rate / hour';
  slots                 @title : 'Composition';
}

annotate konstryx.master.CrewTemplateSlot with {
  slotNo    @title : 'Slot';
  trade     @title : 'Trade';
  grade     @title : 'Grade';
  isForeman @title : 'Foreman';
  ratePerHr @title : 'Rate / hour';
}

annotate konstryx.master.Gang with {
  code            @title : 'Gang';
  description     @title : 'Description';
  template        @title : 'Crew template';
  project         @title : 'Project';
  manned          @title : 'Manned';
  slotsRequired   @title : 'Slots';
  actualRatePerHr @title : 'Actual rate / hour';
  status          @title : 'Status';
  blockedReason   @title : 'Why it cannot work';
  slots           @title : 'Slots';
}

annotate konstryx.master.GangSlot with {
  slotNo        @title : 'Slot';
  source        @title : 'Sourced from';
  employee      @title : 'Worker';
  engagement    @title : 'Engagement';
  trade         @title : 'Slot trade';
  grade         @title : 'Grade';
  ratePerHr     @title : 'Rate / hour';
  blockedReason @title : 'Why he does not count';
}

annotate konstryx.master.AbsenceReason with {
  code                 @title : 'Reason';
  description          @title : 'Description';
  blocksTimesheet      @title : 'Blocks timesheet';
  blocksMobilisation   @title : 'Blocks mobilisation';
  documentRequired     @title : 'Document required';
  postsAsAbsenceHours  @title : 'Posts as absence hours';
  returnsAutomatically @title : 'Returns automatically';
}

annotate konstryx.master.Absence with {
  employee   @title : 'Worker';
  engagement @title : 'Engagement';
  reason     @title : 'Reason';
  fromDate   @title : 'From';
  toDate     @title : 'To';
  derived    @title : 'Raised by an expiry';
  note       @title : 'Note';
}

annotate konstryx.master.SubcontractWorker with {
  workerNo    @title : 'Worker number';
  fullName    @title : 'Name';
  passportNo  @title : 'Passport';
  emiratesId  @title : 'Emirates ID';
  nationality @title : 'Nationality';
  status      @title : 'Status';
  documents   @title : 'Documents';
  engagements @title : 'Engagements';
}

annotate konstryx.master.SubcontractWorkerDocument with {
  code        @title : 'Document';
  description @title : 'Description';
  documentNo  @title : 'Number';
  issuedOn    @title : 'Issued';
  expiresOn   @title : 'Expires';
  blocking    @title : 'Stops him working';
}

annotate konstryx.master.SubcontractEngagement with {
  worker         @title : 'Worker';
  vendor         @title : 'Supplier';
  project        @title : 'Project';
  poNo           @title : 'Purchase order';
  poItem         @title : 'Item';
  trade          @title : 'Engaged as';
  grade          @title : 'Grade';
  ratePerHr      @title : 'Rate / hour';
  fromDate       @title : 'From';
  toDate         @title : 'To';
  hseInductionOn @title : 'HSE induction';
  wcCoverExpiry  @title : 'WC cover expires';
  status         @title : 'Status';
}

annotate konstryx.master.RosterUpload with {
  vendor        @title : 'Supplier';
  fileName      @title : 'File';
  uploadedOn    @title : 'Uploaded';
  status        @title : 'Status';
  rowsTotal     @title : 'Rows';
  rowsAccepted  @title : 'Accepted';
  rowsRejected  @title : 'Rejected';
  rowsDuplicate @title : 'Already held';
  rows          @title : 'Rows';
}

annotate konstryx.master.RosterUploadRow with {
  lineNo      @title : 'Line';
  fullName    @title : 'Name';
  passportNo  @title : 'Passport';
  tradeCode   @title : 'Trade';
  gradeCode   @title : 'Grade';
  joiningDate @title : 'Joining';
  visaExpiry  @title : 'Visa expires';
  outcome     @title : 'Outcome';
  reason      @title : 'Reason';
  worker      @title : 'Matched to';
}

annotate konstryx.master.AssetRegister with {
  assetNo @title : 'Asset number';
}

annotate konstryx.mat.PullRequest with {
  docNo           @title : 'Pull request';
  reservationLine @title : 'Reservation line';
  storageLoc      @title : 'Storage location';
  qtyRequested    @title : 'Quantity requested';
  qtyIssued       @title : 'Quantity issued';
  issuedValue     @title : 'Issued value';
  s4GIDoc         @title : 'ERP goods issue document';
  s4GIDate        @title : 'ERP goods issue date';
  s4GIQty         @title : 'ERP goods issue quantity';
  s4System        @title : 'ERP system';
  syncMessage     @title : 'ERP message';
  status          @title : 'Status';
}

annotate konstryx.mat.SiteReceipt with {
  pullRequest     @title : 'Pull request';
  confirmedOnSite @title : 'Confirmed on site';
  receivedQty     @title : 'Received quantity';
  shortQty        @title : 'Outstanding after this';
  note            @title : 'Note';
  receivedBy      @title : 'Received by';
  receivedOn      @title : 'Received on';
}

annotate konstryx.mat.ConsumptionRecord with {
  reservationLine  @title : 'Reservation line';
  recordDate       @title : 'Record date';
  diaryOutputQty   @title : 'Diary output quantity';
  theoreticalQty   @title : 'Theoretical quantity';
  actualQty        @title : 'Actual quantity';
  wastageAllowance @title : 'Wastage allowance';
  rateApplied      @title : 'Norm applied';
  variance         @title : 'Variance';
  variancePct      @title : 'Variance %';
  result           @title : 'Result';
  recordedBy       @title : 'Recorded by';
  note             @title : 'Note';
}

annotate konstryx.wf.ReservationVariation with {
  reservation   @title : 'Reservation';
  reason        @title : 'Reason';
  narrative     @title : 'What changed';
  effectiveFrom @title : 'Effective from';
  decidedBy     @title : 'Decided by';
  decidedOn     @title : 'Decided on';
  deltaAmount   @title : 'Change in value';
  lines         @title : 'Lines';
}

annotate konstryx.wf.ReservationVariationLine with {
  variation        @title : 'Variation';
  reservationLine  @title : 'Reservation line';
  qtyBefore        @title : 'Quantity before';
  qtyAfter         @title : 'Quantity after';
  rateBefore       @title : 'Rate before';
  rateAfter        @title : 'Rate after';
  daysBefore       @title : 'Days before';
  daysAfter        @title : 'Days after';
  encumberedBefore @title : 'Locked before';
  encumberedAfter  @title : 'Locked after';
  delta            @title : 'Change';
}

annotate konstryx.mat.ReservationClosure with {
  reservation    @title : 'Reservation';
  finalActual    @title : 'Final actual';
  theoretical    @title : 'Theoretical';
  variance       @title : 'Variance';
  releasedAmount @title : 'Released amount';
  result         @title : 'Result';
  postedBy       @title : 'Posted by';
  postedOn       @title : 'Posted on';
}

annotate konstryx.mat.PurchaseRequisition with {
  prNo          @title : 'PR number';
  status        @title : 'Status';
  sourceRequest @title : 'Source request';
  project       @title : 'Project';
  company       @title : 'Company';
  raisedBy      @title : 'Raised by';
  raisedOn      @title : 'Raised on';
  lines         @title : 'Lines';
}

annotate konstryx.mat.PurchaseRequisitionLine with {
  parent       @title : 'Parent';
  lineNo       @title : 'Line number';
  resource     @title : 'Resource';
  material     @title : 'Material';
  description  @title : 'Description';
  wbs          @title : 'WBS';
  cbs          @title : 'CBS';
  sourceLine   @title : 'Source line';
  qtyProcure   @title : 'Quantity to procure';
  uom          @title : 'Unit of measure';
  estUnitPrice @title : 'Estimated unit price';
  estTotal     @title : 'Estimated total';
  needBy       @title : 'Needed by';
  status       @title : 'Status';
  approverRole @title : 'Approver role';
}

annotate konstryx.mat.PurchaseOrder with {
  poNo              @title : 'PO number';
  vendor            @title : 'Vendor';
  status            @title : 'Status';
  sourceRequisition @title : 'Source requisition';
  project           @title : 'Project';
  company           @title : 'Company';
  orderedOn         @title : 'Ordered on';
  lines             @title : 'Lines';
}

annotate konstryx.mat.PurchaseOrderLine with {
  parent       @title : 'Parent';
  lineNo       @title : 'Line number';
  material     @title : 'Material';
  resource     @title : 'Resource';
  description  @title : 'Description';
  wbs          @title : 'WBS';
  cbs          @title : 'CBS';
  sourcePRLine @title : 'Source PR line';
  qty          @title : 'Quantity';
  openQty      @title : 'Open quantity';
  netValue     @title : 'Net value';
  eta          @title : 'ETA';
  acknowledged @title : 'Acknowledged';
  paymentTerms @title : 'Payment terms';
  status       @title : 'Status';
}

annotate konstryx.mat.GoodsReceipt with {
  grDoc         @title : 'Goods receipt document';
  po            @title : 'Purchase order';
  poLineNo      @title : 'PO line number';
  poLine        @title : 'PO line';
  grQty         @title : 'Goods receipt quantity';
  grValue       @title : 'Goods receipt value';
  datePosted    @title : 'Date posted';
  threeWayMatch @title : 'Three-way match';
  matchVariance @title : 'Match variance';
}

annotate konstryx.mat.SupplierInvoice with {
  invoiceNo   @title : 'Invoice number';
  vendor      @title : 'Vendor';
  po          @title : 'Purchase order';
  project     @title : 'Project';
  company     @title : 'Company';
  postingDate @title : 'Posting date';
  netAmount   @title : 'Net amount';
  status      @title : 'Status';
  matched     @title : 'Matched';
  lines       @title : 'Lines';
}

annotate konstryx.mat.SupplierInvoiceLine with {
  parent       @title : 'Invoice';
  lineNo       @title : 'Line';
  poLine       @title : 'PO line';
  poLineNo     @title : 'PO line number';
  goodsReceipt @title : 'Goods receipt';
  description  @title : 'Description';
  qty          @title : 'Quantity';
  netAmount    @title : 'Net amount';
  matched      @title : 'Matched';
  variance     @title : 'Variance';
}

annotate konstryx.mat.RfqEvent with {
  eventNo @title : 'Event number';
}

annotate konstryx.mat.Quotation with {
  quoteNo @title : 'Quote number';
}

annotate konstryx.mat.BidAnalysis with {
  boqRef       @title : 'BOQ reference';
  localContent @title : 'Local content';
}

annotate konstryx.mpr.ManpowerRequestLine with {
  line           @title : 'Line';
  heads          @title : 'Heads';
  tradeGrade     @title : 'Trade grade';
  sourceType     @title : 'Source type';
  vendor         @title : 'Vendor';
  crewId         @title : 'Crew ID';
  crewLead       @title : 'Crew lead';
  mobDate        @title : 'Mobilisation date';
  demobDate      @title : 'Demobilisation date';
  durationDays   @title : 'Duration (days)';
  ratePerHeadDay @title : 'Rate per head-day';
  inductionState @title : 'Induction state';
  timesheets     @title : 'Timesheets';
}

annotate konstryx.mpr.TimesheetEntry with {
  manpowerLine @title : 'Manpower line';
  workDate     @title : 'Date';
  headsPresent @title : 'Heads present';
  regularHrs   @title : 'Regular hours';
  otHrs        @title : 'Overtime hours';
  wbs          @title : 'WBS';
  cbs          @title : 'CBS';
  activity     @title : 'Activity';
  location     @title : 'Location';
  costAmount   @title : 'Cost';
  logStatus    @title : 'Status';
  signedBy     @title : 'Signed by';
}

annotate konstryx.mpr.ProductivitySnapshot with {
  project       @title : 'Project';
  location      @title : 'Location';
  locationCode  @title : 'Location';
  locationName  @title : 'Location name';
  locationType  @title : 'Location type';
  takenAt       @title : 'Measured at';
  signedDays    @title : 'Signed days';
  headDays      @title : 'Head-days';
  labourHours   @title : 'Labour hours';
  labourCost    @title : 'Labour cost';
  installedQty  @title : 'Installed quantity';
  uom           @title : 'Unit of measure';
  outputPerHour @title : 'Output per hour';
  costPerUnit   @title : 'Cost per unit';
  note          @title : 'Note';
}

annotate konstryx.nr.NumberRangeObject with {
  code        @title : 'Code';
  name        @title : 'Name';
  entityName  @title : 'Entity name';
  scope       @title : 'Scope';
  pattern     @title : 'Pattern';
  resetPolicy @title : 'Reset policy';
  seqLength   @title : 'Sequence length';
  startAt     @title : 'Start at';
  isActive    @title : 'Active';
  counters    @title : 'Counters';
}

annotate konstryx.nr.NumberRangeCounter with {
  rangeObject @title : 'Range object';
  companyCode @title : 'Company code';
  fiscalYear  @title : 'Fiscal year';
  lastNumber  @title : 'Last number';
}

annotate konstryx.prj.Project with {
  code             @title : 'Code';
  name             @title : 'Name';
  company          @title : 'Company';
  customerParent   @title : 'Customer parent';
  contractValue    @title : 'Contract value';
  ccy              @title : 'Currency';
  startDate        @title : 'Start date';
  endDate          @title : 'End date';
  contractFx       @title : 'Contract FX';
  budgetFx         @title : 'Budget FX';
  stage            @title : 'Stage';
  executingCompany @title : 'Executing company';
  childProjects    @title : 'Child projects';
  parentProject    @title : 'Parent project';
  wbsElements      @title : 'WBS elements';
  boqs             @title : 'Bills of quantities';
  cbs              @title : 'CBS';
  activities       @title : 'Activities';
  locations        @title : 'Locations';
}

annotate konstryx.prj.WBSElement with {
  code         @title : 'Code';
  project      @title : 'Project';
  parent       @title : 'Parent';
  activityType @title : 'Activity type';
  description  @title : 'Description';
  activities   @title : 'Activities';
}

annotate konstryx.prj.Activity with {
  code          @title : 'Code';
  name          @title : 'Name';
  project       @title : 'Project';
  wbs           @title : 'WBS';
  durationDays  @title : 'Duration (days)';
  plannedStart  @title : 'Planned start';
  plannedFinish @title : 'Planned finish';
  earlyStart    @title : 'Early start';
  earlyFinish   @title : 'Early finish';
  lateStart     @title : 'Late start';
  lateFinish    @title : 'Late finish';
  totalFloat    @title : 'Total float';
  freeFloat     @title : 'Free float';
  isCritical    @title : 'On the critical path';
  actualStart   @title : 'Actual start';
  actualFinish  @title : 'Actual finish';
  percentDone   @title : 'Percent done';
  status        @title : 'Status';
  predecessors  @title : 'Predecessors';
  successors    @title : 'Successors';
}

annotate konstryx.prj.ActivityRelation with {
  predecessor @title : 'Predecessor';
  successor   @title : 'Successor';
  linkType    @title : 'Link type';
  lagDays     @title : 'Lag (days)';
}

annotate konstryx.prj.BOQ with {
  boqId         @title : 'BOQ ID';
  project       @title : 'Project';
  version       @title : 'Version';
  status        @title : 'Status';
  contractValue @title : 'Contract value';
  source        @title : 'Source';
  items         @title : 'Items';
}

annotate konstryx.prj.BOQItem with {
  boq          @title : 'BOQ';
  itemNo       @title : 'Item number';
  code         @title : 'Code';
  description  @title : 'Description';
  qty          @title : 'Quantity';
  budgetQty    @title : 'Budgeted quantity';
  uom          @title : 'Unit of measure';
  rate         @title : 'Rate';
  amount       @title : 'Amount';
  billedToDate @title : 'Billed to date';
  cumDoneQty   @title : 'Quantity done to date';
  cumDonePct   @title : 'Percent done to date';
  certifiedPct @title : 'Certified %';
  cbs          @title : 'CBS';
  buildUp      @title : 'Build-up';
}

annotate konstryx.prj.BOQItemResource with {
  boqItem       @title : 'BOQ item';
  resource      @title : 'Resource';
  category      @title : 'Category';
  qtyPerUom     @title : 'Quantity per UoM';
  totalQty      @title : 'Total quantity';
  uom           @title : 'Unit of measure';
  unitRate      @title : 'Unit rate';
  amountPerUnit @title : 'Amount per unit';
  totalAmount   @title : 'Total';
  source        @title : 'Source';
  sourceNorm    @title : 'Source norm';
  difficultyPct @title : 'Difficulty %';
  difficultySrc @title : 'Difficulty src';
  basis         @title : 'Basis';
}

annotate konstryx.prj.CBSInstance with {
  code         @title : 'Code';
  project      @title : 'Project';
  parent       @title : 'Parent';
  libraryNode  @title : 'Library node';
  budgetAmount @title : 'Budget amount';
  ownAmount    @title : 'Own amount';
  costNature   @title : 'Cost nature';
  allocBasis   @title : 'Allocation basis';
  level        @title : 'Level';
  children     @title : 'Children';
}

annotate konstryx.prj.SiteLocation with {
  project      @title : 'Project';
  code         @title : 'Code';
  name         @title : 'Name';
  level        @title : 'Level';
  locationType @title : 'Location type';
  parent       @title : 'Parent';
  children     @title : 'Children';
  gfa          @title : 'GFA';
  uom          @title : 'Unit of measure';
}

annotate konstryx.prj.Allocation with {
  boqItem      @title : 'BOQ item';
  wbs          @title : 'WBS';
  cbs          @title : 'CBS';
  allocQty     @title : 'Allocation quantity';
  allocPct     @title : 'Allocation %';
  pctOfItem    @title : '% of item';
  pctOfCBSRate @title : '% of cbsrate';
  template     @title : 'Template';
  splitBasis   @title : 'Split basis';
  location     @title : 'Location';
}

annotate konstryx.prj.ProjectResource with {
  project    @title : 'Project';
  wbs        @title : 'WBS';
  resource   @title : 'Resource';
  plannedQty @title : 'Planned quantity';
  uom        @title : 'Unit of measure';
  buildUp    @title : 'Build-up';
}

annotate konstryx.scr.SubcontractRequest with {
  scopeDescription @title : 'Scope description';
  vendorBPNo       @title : 'Vendor bpno';
  vendorName       @title : 'Vendor name';
  isGroupCompany   @title : 'Is group company';
  executingCompany @title : 'Executing company';
  contractValue    @title : 'Contract value';
  ccy              @title : 'Currency';
  applications     @title : 'Applications';
}

annotate konstryx.scr.PaymentApplication with {
  scr           @title : 'Subcontract request';
  paNo          @title : 'PA number';
  claimedAmount @title : 'Claimed amount';
  status        @title : 'Status';
  certificates  @title : 'Certificates';
}

annotate konstryx.scr.PaymentCertificate with {
  pa              @title : 'Payment application';
  scr             @title : 'Subcontract request';
  certSeq         @title : 'Certificate number';
  certOf          @title : 'Certificates in total';
  claimedGross    @title : 'Claimed gross';
  adjustment      @title : 'Adjustment';
  certifiedGross  @title : 'Certified gross';
  retentionPct    @title : 'Retention %';
  retentionAmount @title : 'Retention';
  netCertified    @title : 'Net certified';
  ldApplied       @title : 'Liquidated damages';
  backChargeTotal @title : 'Back charges';
  s4InvoiceRef    @title : 'ERP invoice reference';
  s4Api           @title : 'ERP API';
  paymentTerm     @title : 'Payment term';
  adjustments     @title : 'Adjustment lines';
  ldSteps         @title : 'LD calculation steps';
  backCharges     @title : 'Back charge lines';
  signOffs        @title : 'Sign-offs';
}

annotate konstryx.scr.CertAdjustmentLine with {
  pc           @title : 'Payment certificate';
  subBoqLine   @title : 'Sub BOQ line';
  description  @title : 'Description';
  claimedQty   @title : 'Claimed quantity';
  certifiedQty @title : 'Certified quantity';
  deltaQty     @title : 'Delta quantity';
  uom          @title : 'Unit of measure';
  reason       @title : 'Reason';
}

annotate konstryx.scr.LDCalculationStep with {
  pc       @title : 'Payment certificate';
  stepNo   @title : 'Step number';
  step     @title : 'Step';
  basis    @title : 'Basis';
  value    @title : 'Value';
  emphasis @title : 'Emphasis';
}

annotate konstryx.scr.BackChargeLine with {
  pc           @title : 'Payment certificate';
  description  @title : 'Description';
  cause        @title : 'Cause';
  rechargeType @title : 'Recharge type';
  qtyBasis     @title : 'Quantity basis';
  rate         @title : 'Rate';
  amount       @title : 'Amount';
}

annotate konstryx.scr.CertSignOff with {
  pc        @title : 'Payment certificate';
  seq       @title : 'Sequence';
  role      @title : 'Role';
  name      @title : 'Name';
  decision  @title : 'Decision';
  decidedOn @title : 'Decided on';
}

annotate konstryx.sf.ScaffoldDesignRequestLine with {
  line        @title : 'Line';
  deliverable @title : 'Deliverable';
  loadClass   @title : 'Load class';
  engineer    @title : 'Engineer';
  dueDate     @title : 'Due date';
  approvedOn  @title : 'Approved on';
}

annotate konstryx.sf.ScaffoldMaterialRequestLine with {
  line            @title : 'Line';
  elementType     @title : 'Element type';
  bookingStart    @title : 'Booking start';
  bookingEnd      @title : 'Booking end';
  sourceType      @title : 'Source type';
  vendor          @title : 'Vendor';
  ratePerDayUnit  @title : 'Rate per unit-day';
  returnedQty     @title : 'Returned quantity';
  returnCondition @title : 'Return condition';
}

annotate konstryx.sys.ContentPack with {
  packId       @title : 'Content pack';
  version      @title : 'Version';
  description  @title : 'Description';
  appliedAt    @title : 'Applied at';
  appliedBy    @title : 'Applied by';
  rowsInserted @title : 'Rows inserted';
  rowsSkipped  @title : 'Rows already present';
}

annotate konstryx.sys.ImportRun with {
  target       @title : 'Target';
  fileName     @title : 'File name';
  rowsTotal    @title : 'Rows';
  rowsAccepted @title : 'Accepted';
  rowsRejected @title : 'Rejected';
  mode         @title : 'Mode';
  status       @title : 'Status';
  message      @title : 'Message';
  rows         @title : 'Rows';
}

annotate konstryx.sys.ImportRow with {
  run      @title : 'Run';
  lineNo   @title : 'Line number';
  payload  @title : 'Payload';
  accepted @title : 'Accepted';
  error    @title : 'Error';
}

annotate konstryx.sys.Attachment with {
  entityName  @title : 'Entity name';
  objectID    @title : 'Object';
  objectDocNo @title : 'Document number';
  fileName    @title : 'File name';
  mimeType    @title : 'File type';
  content     @title : 'File';
  fileSize    @title : 'Size';
  category    @title : 'Category';
  note        @title : 'Note';
  version     @title : 'Version';
  supersedes  @title : 'Supersedes';
}

annotate konstryx.sys.AttachmentCategory with {
  code        @title : 'Code';
  name        @title : 'Name';
  authObject  @title : 'Authorisation object';
  isMandatory @title : 'Mandatory';
  isActive    @title : 'Active';
}

annotate konstryx.sys.UserVariant with {
  user        @title : 'User';
  target      @title : 'Target';
  variantName @title : 'Variant';
  payload     @title : 'Payload';
  isDefault   @title : 'Default';
  isPublic    @title : 'Shared with everyone';
}

annotate konstryx.wf.ResourceRequest with {
  verticalType   @title : 'Vertical type';
  wbs            @title : 'WBS';
  needBy         @title : 'Needed by';
  isSubstitution @title : 'Is substitution';
  prFlag         @title : 'PR flag';
  lines          @title : 'Lines';
  attachments    @title : 'Attachments';
}

annotate konstryx.wf.ResourceRequestLine with {
  parent      @title : 'Parent';
  lineNo      @title : 'Line number';
  resource    @title : 'Resource';
  description @title : 'Description';
  qty         @title : 'Quantity';
  uom         @title : 'Unit of measure';
  wbs         @title : 'WBS';
  cbs         @title : 'CBS';
  estUnitCost @title : 'Estimated unit cost';
  estTotal    @title : 'Estimated total';
  needBy      @title : 'Needed by';
  lineStatus  @title : 'Line status';
  advisory    @title : 'Advisory';
  avcResult   @title : 'AVC result';
}

annotate konstryx.wf.AdvisoryDecision with {
  rr        @title : 'Resource request';
  line      @title : 'Line';
  decision  @title : 'Decision';
  decidedBy @title : 'Decided by';
  decidedOn @title : 'Decided on';
  rationale @title : 'Rationale';
}

annotate konstryx.wf.AvailabilityCheck with {
  rr    @title : 'Resource request';
  lines @title : 'Lines';
}

annotate konstryx.wf.AvailabilityCheckLine with {
  parent      @title : 'Parent';
  rrLine      @title : 'RR line';
  atpQty      @title : 'ATP quantity';
  stockQty    @title : 'Stock quantity';
  expectedQty @title : 'Expected quantity';
  storageLoc  @title : 'Storage location';
  result      @title : 'Result';
}

annotate konstryx.wf.Reservation with {
  rr            @title : 'Resource request';
  executionFlow @title : 'Execution flow';
  lines         @title : 'Lines';
}

annotate konstryx.wf.ReservationLine with {
  reservation      @title : 'Reservation';
  rrLine           @title : 'RR line';
  resource         @title : 'Resource';
  qty              @title : 'Quantity';
  uom              @title : 'Unit of measure';
  dailyRate        @title : 'Daily rate';
  encumberedAmount @title : 'Encumbered';
  consumedToDate   @title : 'Consumed to date';
  burnPct          @title : 'Burn %';
  costToDate       @title : 'Cost to date';
  drift            @title : 'Drift';
  lineStatus       @title : 'Line status';
}

annotate konstryx.wf.StatusHistory with {
  docType   @title : 'Document type';
  docId     @title : 'Document';
  fromState @title : 'From state';
  toState   @title : 'To state';
  changedBy @title : 'Changed by';
  changedOn @title : 'Changed on';
  comment   @title : 'Comment';
}

annotate konstryx.wf.DocumentLink with {
  fromDoc  @title : 'From document';
  toDoc    @title : 'To document';
  linkType @title : 'Link type';
}

