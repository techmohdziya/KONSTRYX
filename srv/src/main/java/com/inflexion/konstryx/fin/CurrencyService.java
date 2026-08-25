package com.inflexion.konstryx.fin;

import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;

/**
 * Converts money between currencies, and says which rate it used.
 *
 * Currency codes were already carried on projects, companies, rates and
 * approval bands, and nothing converted between them. Comparing them as bare
 * numbers is silently correct while a group trades in one currency and silently
 * wrong afterwards — which is the worst kind of wrong, because nothing about
 * the output changes shape when it starts being false.
 *
 * Every conversion returns the rate it used alongside the amount. A converted
 * figure whose rate nobody can name cannot be reconciled against anyone else's,
 * so the rate travels with the money rather than being left behind here.
 */
@Component
public class CurrencyService {

    private static final String E_RATE = "konstryx.fin.ExchangeRate";

    /** Money is held to two places; the rate itself keeps six. */
    private static final int MONEY_SCALE = 2;

    @Autowired
    private PersistenceService db;

    /**
     * The rate used for one conversion, and where it came from.
     *
     * A record rather than a bare BigDecimal because the caller nearly always
     * has to report the rate as well as apply it.
     */
    public record Conversion(
            BigDecimal amount,
            String ccy,
            BigDecimal rate,
            String rateType,
            LocalDate validFrom,
            String source) {

        /** True when no conversion was needed — same currency, rate 1. */
        public boolean isIdentity() {
            return "IDENTITY".equals(source);
        }
    }

    /**
     * Converts an amount, or throws if no rate covers the pair on that date.
     *
     * Refusing is deliberate. A missing rate returned as null invites the
     * caller to fall back on the unconverted number, which is the exact
     * mistake this class exists to prevent — the figure would look plausible
     * and be denominated in the wrong currency.
     */
    public Conversion convert(BigDecimal amount, String fromCcy, String toCcy,
                              String rateType, LocalDate asOf) {
        if (amount == null) {
            return null;
        }
        String from = normalise(fromCcy);
        String to = normalise(toCcy);
        LocalDate when = asOf == null ? LocalDate.now() : asOf;
        String kind = isBlank(rateType) ? "SPOT" : rateType.trim().toUpperCase();

        // Same currency, or a currency nobody stated. An amount with no
        // currency is treated as already being in the target: the alternative
        // is to refuse every legacy row, and the caller's own comparison was
        // single-currency before this class existed.
        if (from == null || to == null || from.equals(to)) {
            return new Conversion(amount.setScale(MONEY_SCALE, RoundingMode.HALF_UP),
                    to == null ? from : to, BigDecimal.ONE, kind, when, "IDENTITY");
        }

        Row rate = latestRate(from, to, kind, when);
        if (rate != null) {
            return apply(amount, to, rate, kind, false);
        }

        // The inverse pair. A table holding EUR->AED and asked for AED->EUR
        // has the answer; making someone maintain both directions is how they
        // drift apart.
        Row inverse = latestRate(to, from, kind, when);
        if (inverse != null) {
            return apply(amount, to, inverse, kind, true);
        }

        throw new ServiceException(ErrorStatuses.BAD_REQUEST, String.format(
                "No %s rate is on file for %s to %s on %s. An administrator must "
                        + "maintain one before amounts in %s can be compared with %s.",
                kind, from, to, when, from, to));
    }

    /** Convenience for the common case: today's spot rate. */
    public Conversion convert(BigDecimal amount, String fromCcy, String toCcy) {
        return convert(amount, fromCcy, toCcy, "SPOT", null);
    }

    /**
     * Converts for comparison, and falls back to the raw amount when no rate
     * exists — for callers that must not fail closed.
     *
     * Used where refusing would block a business action that has nothing to do
     * with currency, such as submitting a document for approval in a tenant
     * that has never maintained a rate table. The fallback is not silent: the
     * returned Conversion carries source UNCONVERTED so the caller can say so.
     */
    public Conversion convertOrPass(BigDecimal amount, String fromCcy, String toCcy,
                                    String rateType, LocalDate asOf) {
        try {
            return convert(amount, fromCcy, toCcy, rateType, asOf);
        } catch (ServiceException e) {
            return new Conversion(
                    amount == null ? null : amount.setScale(MONEY_SCALE, RoundingMode.HALF_UP),
                    normalise(fromCcy), BigDecimal.ONE,
                    isBlank(rateType) ? "SPOT" : rateType.trim().toUpperCase(),
                    asOf == null ? LocalDate.now() : asOf, "UNCONVERTED");
        }
    }

    // ---------------------------------------------------------------- internals

    /**
     * The most recent rate of that kind valid on or before the date.
     *
     * A rate applies from its validFrom until a later one supersedes it, so
     * "the rate on 12 March" is the newest row not after 12 March — not a row
     * dated exactly that day, which usually does not exist.
     */
    private Row latestRate(String from, String to, String kind, LocalDate asOf) {
        Row best = null;
        LocalDate bestFrom = null;
        for (Row row : db.run(Select.from(E_RATE)
                .where(r -> r.get("fromCcy_code").eq(from)
                        .and(r.get("toCcy_code").eq(to))))) {
            if (!kind.equalsIgnoreCase(str(row.get("rateType")))) {
                continue;
            }
            LocalDate validFrom = date(row.get("validFrom"));
            if (validFrom != null && validFrom.isAfter(asOf)) {
                continue;
            }
            if (bestFrom == null || validFrom == null
                    || validFrom.isAfter(bestFrom)) {
                best = row;
                bestFrom = validFrom;
            }
        }
        return best;
    }

    private Conversion apply(BigDecimal amount, String toCcy, Row row,
                             String kind, boolean inverted) {
        BigDecimal rate = decimal(row.get("rate"));
        if (rate == null || rate.signum() <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The exchange rate on file is zero or negative and cannot be applied.");
        }
        // Inverting keeps the full six places before the multiply, so a round
        // trip through the inverse pair lands back on the original amount.
        BigDecimal effective = inverted
                ? BigDecimal.ONE.divide(rate, 12, RoundingMode.HALF_UP)
                : rate;
        String source = str(row.get("source"));
        return new Conversion(
                amount.multiply(effective).setScale(MONEY_SCALE, RoundingMode.HALF_UP),
                toCcy,
                effective.setScale(6, RoundingMode.HALF_UP),
                kind,
                date(row.get("validFrom")),
                inverted ? (isBlank(source) ? "inverted" : source + " (inverted)") : source);
    }

    private static String normalise(String ccy) {
        return isBlank(ccy) ? null : ccy.trim().toUpperCase();
    }

    private static LocalDate date(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof LocalDate d) {
            return d;
        }
        try {
            return LocalDate.parse(String.valueOf(value));
        } catch (RuntimeException e) {
            return null;
        }
    }

    private static BigDecimal decimal(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof BigDecimal d) {
            return d;
        }
        try {
            return new BigDecimal(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
