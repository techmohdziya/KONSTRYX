package com.inflexion.konstryx.sys;

import org.h2.tools.Server;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

import java.sql.SQLException;

/**
 * Opens the local database to a SQL client, for development only.
 *
 * The database this service runs on locally lives in the heap of this process.
 * That is the right arrangement - it costs nothing to start, it is identical
 * on every machine, and it cannot accumulate the half-migrated state that
 * makes one developer's copy behave differently from everybody else's. It has
 * one consequence: a tool running in another process cannot see it at all. An
 * in-memory H2 database is reachable only from the JVM that created it, so
 * DBeaver pointed at this service finds nothing, and pointed at a file finds
 * no file.
 *
 * This starts H2's TCP listener inside this JVM, which lets a client outside
 * it attach to the same in-memory database over a socket. Nothing about the
 * data changes: it is still in memory, still seeded from db/data and
 * test/data on every boot, and still gone when the process stops.
 *
 * Bound to localhost. The listener is started without -tcpAllowOthers, so it
 * refuses connections from anywhere but this machine - the database holds a
 * demo dataset and no credentials, but a listener on an interface is a
 * listener somebody else can reach, and the person who needs it is sitting at
 * the keyboard.
 *
 * Development profile only, and deliberately so. On Cloud Foundry the service
 * runs on SAP HANA Cloud, which has its own access path and its own
 * authorization; a second door into the database, opened by the application
 * itself and authenticated by nothing, is not something that should exist
 * where real data does.
 */
@Configuration
@Profile("default")
public class H2TcpServer {

    private static final Logger log = LoggerFactory.getLogger(H2TcpServer.class);

    @Value("${konstryx.h2.tcp-port:9092}")
    private String port;

    @Value("${spring.datasource.url:}")
    private String url;

    /**
     * Started and stopped with the context, so the listener never outlives the
     * database it serves. A client left connected to a stopped service gets a
     * refused socket rather than a silent read of nothing.
     */
    // Named for what it is rather than after the class, because Spring
    // registers the configuration class under its own decapitalised name and
    // a @Bean method spelt the same way collides with it.
    @Bean(initMethod = "start", destroyMethod = "stop")
    public Server h2SqlClientListener() throws SQLException {
        Server server = Server.createTcpServer("-tcp", "-tcpPort", port, "-ifNotExists");
        log.info("H2 open to SQL clients on localhost:{} - connect with {}",
                port, clientUrl());
        return server;
    }

    /** The URL to paste into a client, built from the one this service uses. */
    private String clientUrl() {
        // jdbc:h2:mem:konstryx;... -> jdbc:h2:tcp://localhost:9092/mem:konstryx
        String name = url.startsWith("jdbc:h2:") ? url.substring("jdbc:h2:".length()) : url;
        int semicolon = name.indexOf(';');
        if (semicolon >= 0) {
            name = name.substring(0, semicolon);
        }
        return "jdbc:h2:tcp://localhost:" + port + "/" + name;
    }
}
