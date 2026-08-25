package com.inflexion.konstryx.fin;

import com.sap.cds.services.EventContext;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Exposes currency conversion as a service action.
 *
 * It is an action rather than an internal helper because every screen that
 * shows a converted figure has to be able to state the rate it used. A number
 * whose rate nobody can name cannot be reconciled against anyone else's, and
 * two reports run a day apart on the same period will differ with no way of
 * telling whether the difference is the money or the rate.
 */
@Component
@ServiceName("AdminService")
public class ConvertHandler implements EventHandler {

    @Autowired
    private CurrencyService currency;

    @On(event = "convert")
    public void onConvert(EventContext context) {
        BigDecimal amount = decimal(context.get("amount"));
        String from = str(context.get("fromCcy"));
        String to = str(context.get("toCcy"));
        String rateType = str(context.get("rateType"));
        LocalDate asOf = date(context.get("asOf"));

        // Deliberately the strict conversion, not convertOrPass: a caller that
        // asked for a conversion outright wants to be told when there is no
        // rate, rather than handed back the amount it already had.
        CurrencyService.Conversion converted =
                currency.convert(amount, from, to, rateType, asOf);

        Map<String, Object> result = new LinkedHashMap<>();
        if (converted != null) {
            result.put("amount", converted.amount());
            result.put("ccy", converted.ccy());
            result.put("rate", converted.rate());
            result.put("rateType", converted.rateType());
            result.put("validFrom", converted.validFrom());
            result.put("source", converted.source());
        }
        context.put("result", result);
        context.setCompleted();
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

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
