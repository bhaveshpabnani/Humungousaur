import Foundation

final class PrintScanCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var activeJobs: Set<String> = []
    private var defaultPrinterHash = ""
    private var baselineReady = false

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleDefaultPrinter(emitInitial: emitInitial)
        let jobs = activePrintJobSignatures()
        if !baselineReady {
            activeJobs = jobs
            baselineReady = true
            if emitInitial {
                for job in jobs {
                    emitJob(stimulusType: "print_job_started", jobSignature: job)
                }
            }
            return
        }
        for job in jobs.subtracting(activeJobs) {
            emitJob(stimulusType: "print_job_started", jobSignature: job)
        }
        for job in activeJobs.subtracting(jobs) {
            emitJob(stimulusType: "print_job_completed", jobSignature: job)
        }
        activeJobs = jobs
    }

    private func sampleDefaultPrinter(emitInitial: Bool) {
        guard let hash = defaultPrinterSignature(), emitInitial || defaultPrinterHash != hash else {
            return
        }
        defaultPrinterHash = hash
        spool.append(
            collector: "print_scan_activity",
            source: "system",
            stimulusType: "printer_selected",
            text: "Default printer metadata changed.",
            metadata: [
                "native_source": "macos_cups_print_system",
                "source_api": "lpstat",
                "privacy_level": "redacted",
                "printer_name_omitted": "true",
                "printer_signature_hash": hash,
            ],
            payload: ["printer_signature_hash": hash]
        )
        health.noteEvent()
    }

    private func emitJob(stimulusType: String, jobSignature: String) {
        spool.append(
            collector: "print_scan_activity",
            source: "system",
            stimulusType: stimulusType,
            text: "Print job metadata changed.",
            metadata: [
                "native_source": "macos_cups_print_system",
                "source_api": "lpstat",
                "privacy_level": "redacted",
                "document_name_omitted": "true",
                "printer_name_omitted": "true",
                "print_job_signature_hash": jobSignature,
            ],
            payload: ["print_job_signature_hash": jobSignature]
        )
        health.noteEvent()
    }
}
