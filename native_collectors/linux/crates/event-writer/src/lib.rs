use std::collections::BTreeMap;
use std::fs::{create_dir_all, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct CollectorEventEnvelope {
    pub event_id: String,
    pub collector: String,
    pub source: String,
    pub stimulus_type: String,
    pub privacy_tier: String,
    pub occurred_at: String,
    pub received_at: String,
    pub signature: String,
    pub text: String,
    pub metadata: BTreeMap<String, String>,
    pub payload: BTreeMap<String, String>,
}

impl CollectorEventEnvelope {
    pub fn metadata_event(
        event_id: impl Into<String>,
        collector: impl Into<String>,
        source: impl Into<String>,
        stimulus_type: impl Into<String>,
        occurred_at: impl Into<String>,
        signature: impl Into<String>,
        text: impl Into<String>,
    ) -> Self {
        Self {
            event_id: event_id.into(),
            collector: collector.into(),
            source: source.into(),
            stimulus_type: stimulus_type.into(),
            privacy_tier: "metadata".to_string(),
            occurred_at: occurred_at.into(),
            received_at: String::new(),
            signature: signature.into(),
            text: text.into(),
            metadata: BTreeMap::new(),
            payload: BTreeMap::new(),
        }
    }

    pub fn to_json_line(&self) -> String {
        let received_at = if self.received_at.is_empty() {
            self.occurred_at.as_str()
        } else {
            self.received_at.as_str()
        };
        format!(
            "{{\"event_id\":\"{}\",\"schema_version\":1,\"collector\":\"{}\",\"source\":\"{}\",\"platform\":\"linux\",\"stimulus_type\":\"{}\",\"privacy_tier\":\"{}\",\"occurred_at\":\"{}\",\"received_at\":\"{}\",\"signature\":\"{}\",\"text\":\"{}\",\"metadata\":{},\"payload\":{},\"redaction\":{{\"raw_content_included\":false,\"attention_safe\":true,\"paths_redacted\":true,\"payload_compacted_before_llm\":true,\"privacy_tier\":\"metadata\"}}}}",
            escape(&self.event_id),
            escape(&self.collector),
            escape(&self.source),
            escape(&self.stimulus_type),
            escape(&self.privacy_tier),
            escape(&self.occurred_at),
            escape(received_at),
            escape(&self.signature),
            escape(&self.text),
            string_map_json(&self.metadata),
            string_map_json(&self.payload)
        )
    }
}

pub struct JsonlEventWriter {
    path: PathBuf,
}

impl JsonlEventWriter {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    pub fn append(&self, envelope: &CollectorEventEnvelope) -> io::Result<()> {
        if let Some(parent) = self.path.parent() {
            create_dir_all(parent)?;
        }
        let mut file = OpenOptions::new().create(true).append(true).open(&self.path)?;
        writeln!(file, "{}", envelope.to_json_line())
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}

fn string_map_json(values: &BTreeMap<String, String>) -> String {
    let pairs = values
        .iter()
        .map(|(key, value)| format!("\"{}\":\"{}\"", escape(key), escape(value)))
        .collect::<Vec<_>>()
        .join(",");
    format!("{{{pairs}}}")
}

fn escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}
