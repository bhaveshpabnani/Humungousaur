use event_writer::{CollectorEventEnvelope, JsonlEventWriter};
use std::env;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() -> std::io::Result<()> {
    let data_dir = value_after("--data-dir").unwrap_or_else(|| "artifacts".to_string());
    let now = now_text();
    let mut envelope = CollectorEventEnvelope::metadata_event(
        format!("linux-collector-host-started-{now}"),
        "agent_runtime",
        "system",
        "autonomous_cycle_started",
        now.clone(),
        format!("linux:collector_host_started:{now}"),
        "Linux collector host started.",
    );
    envelope.received_at = now.clone();
    envelope.metadata.insert("helper_id".to_string(), "linux-collector-host".to_string());
    envelope.metadata.insert("helper_version".to_string(), "0.1.0".to_string());
    envelope.metadata.insert("native_source".to_string(), "linux_collector_host_startup".to_string());
    envelope.metadata.insert("raw_content_included".to_string(), "false".to_string());
    envelope.metadata.insert("privacy_level".to_string(), "metadata".to_string());
    let writer = JsonlEventWriter::new(PathBuf::from(data_dir).join("collector_spool").join("agent_runtime.jsonl"));
    writer.append(&envelope)?;
    println!("Humungousaur Linux collector host wrote startup event to {}", writer.path().display());
    Ok(())
}

fn value_after(flag: &str) -> Option<String> {
    let args = env::args().collect::<Vec<_>>();
    args.windows(2)
        .find_map(|window| if window[0] == flag { Some(window[1].clone()) } else { None })
}

fn now_text() -> String {
    match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(duration) => format!("{}", duration.as_secs()),
        Err(_) => "0".to_string(),
    }
}
