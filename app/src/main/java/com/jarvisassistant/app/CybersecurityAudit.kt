package com.jarvisassistant.app

import java.net.InetAddress
import java.net.URL
import javax.net.ssl.HttpsURLConnection

data class AuditFinding(val severity: String, val evidence: String, val impact: String, val remediation: String)
data class AuditReport(val target: String, val tls: String, val addresses: List<String>, val findings: List<AuditFinding>)

/**
 * Passive, single-target checks only: DNS resolution, a normal HTTPS handshake and a
 * HEAD request for security headers. No port scanning, fuzzing, authentication attempts,
 * crawling, exploitation or state-changing requests are made.
 */
object CybersecurityAudit {
    fun run(input: String): AuditReport {
        val host = input.trim().removePrefix("https://").removePrefix("http://").trimEnd('/')
        require(host.isNotBlank() && !host.contains('/') && !host.contains('@') &&
            !host.contains(':') && !host.contains('?') && !host.contains('#')) {
            "Enter one authorized hostname only (for example, example.org)."
        }
        val url = URL("https://$host/")
        require(url.protocol == "https" && url.host.isNotBlank()) { "Only an HTTPS hostname is supported." }

        val addresses = try {
            InetAddress.getAllByName(url.host).map { it.hostAddress }.distinct()
        } catch (e: Exception) {
            throw IllegalStateException("DNS lookup failed: ${e.message ?: "name not found"}")
        }

        val connection = (url.openConnection() as HttpsURLConnection).apply {
            requestMethod = "HEAD"
            connectTimeout = 8_000
            readTimeout = 8_000
            instanceFollowRedirects = false
            setRequestProperty("User-Agent", "JARVIS-Authorized-Security-Review/1.0")
        }
        try {
            val status = connection.responseCode
            val tls = connection.cipherSuite?.let { "HTTPS handshake completed ($it)" }
                ?: "HTTPS handshake completed"
            val findings = mutableListOf<AuditFinding>()
            fun check(header: String, severity: String, remediation: String) {
                val value = connection.getHeaderField(header)
                if (value.isNullOrBlank()) {
                    findings += AuditFinding(
                        severity,
                        "$header: not present in HTTP $status response",
                        "Browsers may lack this defense-in-depth protection for this response.",
                        remediation
                    )
                } else {
                    findings += AuditFinding(
                        "INFO",
                        "$header: ${value.take(180)}",
                        "A response value was observed; presence alone does not prove the policy is correct.",
                        "Review the value against the application's intended behavior."
                    )
                }
            }
            check("Strict-Transport-Security", "MEDIUM", "Serve a carefully scoped HSTS policy over HTTPS after validating all subdomains.")
            check("Content-Security-Policy", "MEDIUM", "Define a restrictive Content-Security-Policy for scripts, styles, frames and connections.")
            check("X-Content-Type-Options", "LOW", "Set X-Content-Type-Options: nosniff.")
            check("Referrer-Policy", "LOW", "Set a restrictive Referrer-Policy, such as strict-origin-when-cross-origin.")
            check("Permissions-Policy", "INFO", "Disable browser features the site does not need with Permissions-Policy.")
            if (status in 300..399) {
                findings += AuditFinding(
                    "INFO",
                    "HEAD returned HTTP $status without following redirects.",
                    "The final destination and its headers were not inspected.",
                    "Review the redirect chain manually and confirm each destination is in scope."
                )
            }
            return AuditReport(url.host, tls, addresses, findings)
        } finally {
            connection.disconnect()
        }
    }
}
