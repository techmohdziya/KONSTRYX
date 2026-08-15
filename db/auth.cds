/**
 * KONSTRYX — konstryx.auth
 * Configurable authorization, administered in the application the way S/4HANA
 * administers authorization objects — not hard-coded into XSUAA scopes.
 *
 * XSUAA still authenticates the user and carries a coarse role that says "this
 * person may reach KONSTRYX at all". Everything finer than that is data:
 * an administrator defines personas, grants each persona activities on
 * authorization objects, and assigns users to personas scoped by company and
 * project. Adding a persona or re-scoping a user must never require a
 * redeploy, because in a per-client deployment the client's own administrator
 * owns that decision.
 *
 * The S/4 analogy is deliberate:
 *   S/4 authorization object   -> auth.AuthObject   (BUDGET, RESERVATION, ...)
 *   S/4 activity (ACTVT)       -> auth.Activity     (01 Create, 03 Display, ...)
 *   S/4 organisational level   -> company + project on auth.UserAssignment
 */
namespace konstryx.auth;

using { cuid, managed, sap.common.CodeList } from '@sap/cds/common';
using { konstryx.admin } from './admin';
using { konstryx.prj } from './prj';

// ---------------------------------------------------------------- catalogue
// Shipped as product content. Clients grant against it; they do not invent it,
// because every entry has to correspond to something the runtime enforces.

/** Functional module — the grouping the administration UI presents. */
entity Module : cuid, managed {
  code        : String(20);          // PRJ · BUD · WF · MAT · EQ · COST · ADM
  name        : String(80);
  sequence    : Integer;
  objects     : Composition of many AuthObject on objects.module = $self;
}

/** A protectable object. One per thing a client may want to restrict. */
entity AuthObject : cuid, managed {
  code                : String(40);  // KX_BUDGET · KX_RESERVATION · KX_COST
  name                : String(80);
  module              : Association to Module;
  /** CDS entity this guards, so the enforcement handler can bind by name. */
  entityName          : String(120); // konstryx.bud.Budget
  /** False for cross-project masters — company scope still applies. */
  projectScoped       : Boolean default true;

  /**
   * How this entity reaches its project and company, as a CDS path from the
   * entity itself. Instance filtering is data-driven for the same reason the
   * grants are: entities reach their project differently — a request holds it
   * directly, a request line reaches it through parent — and encoding thirty
   * such paths in Java would put the enforcement rules somewhere an
   * administrator cannot see them. Null means the dimension does not apply.
   */
  projectPath         : String(120); // project.code · parent.project.code
  companyPath         : String(120); // company.code · parent.company.code

  activities          : Composition of many AuthObjectActivity on activities.authObject = $self;
}

/** Activity codes, mirroring the S/4 ACTVT convention so the numbers read familiar. */
entity Activity : CodeList {
  key code : String(2);              // 01 02 03 06 43 ...
}

/** Which activities a given object actually supports (display-only objects have no 01). */
entity AuthObjectActivity : cuid {
  authObject : Association to AuthObject;
  activity   : Association to Activity;
}

// ------------------------------------------------------------ configuration
// Per deployment. Maintained by the client's administrator at runtime.

/** A named role in the client's own vocabulary — Site Engineer, QS, Cost Controller. */
entity Persona : cuid, managed {
  code        : String(40);
  name        : String(80);
  description : String(255);
  isActive    : Boolean default true;
  /** Set on personas delivered with the product; blocks accidental deletion. */
  isDelivered : Boolean default false;
  permissions : Composition of many PersonaPermission on permissions.persona = $self;
}

/** The grant itself: this persona may perform this activity on this object. */
entity PersonaPermission : cuid, managed {
  persona    : Association to Persona;
  authObject : Association to AuthObject;
  activity   : Association to Activity;
  granted    : Boolean default false;
}

/**
 * User to persona, scoped. A null company means every company in the group;
 * a null project means every project in that company. This is what makes the
 * same persona reusable across a group without cloning it per project.
 */
entity UserAssignment : cuid, managed {
  user      : String(120);
  persona   : Association to Persona;
  company   : Association to admin.Company;      // null = all companies
  project   : Association to prj.Project;        // null = all projects
  validFrom : Date;
  validTo   : Date;
  isActive  : Boolean default true;
}

/**
 * Flattened effective grants for the requesting user, resolved across all of
 * their assignments. The enforcement handler reads this rather than joining
 * four tables per request, and the administration UI uses it to answer
 * "what can this person actually do?" — the question a permission matrix
 * spread over personas and assignments is otherwise very hard to answer.
 */
@readonly
view EffectivePermission as select from UserAssignment as ua
  inner join PersonaPermission as pp on pp.persona.ID = ua.persona.ID
{
  key ua.ID              as assignmentID,
  key pp.ID              as permissionID,
      ua.user            as user            : String(120),
      ua.company.code    as companyCode     : String(10),
      ua.project.code    as projectCode     : String(24),
      ua.validFrom       as validFrom       : Date,
      ua.validTo         as validTo         : Date,
      ua.persona.code    as personaCode     : String(40),
      pp.authObject.code as authObjectCode  : String(40),
      pp.authObject.entityName as entityName : String(120),
      pp.activity.code   as activityCode    : String(2)
}
where ua.isActive = true and pp.granted = true;
