package com.inflexion.konstryx.auth;

/**
 * One resolved row of konstryx.auth.EffectivePermission: this user may perform
 * this activity on this entity, within this company and project scope.
 *
 * A null companyCode means every company; a null projectCode means every
 * project within the company. That is the difference between "Cost Controller
 * for the group" and "Cost Controller on Marina Heights only", and it is the
 * reason scope is nullable rather than a wildcard string.
 */
public record Grant(
        String entityName,
        String authObjectCode,
        String activityCode,
        String companyCode,
        String projectCode) {

    public boolean isCompanyUnrestricted() {
        return companyCode == null || companyCode.isBlank();
    }

    public boolean isProjectUnrestricted() {
        return projectCode == null || projectCode.isBlank();
    }
}
