using System.Text.Json;

namespace Humungousaur.Collectors.EventWriter;

public sealed class JsonlEventWriter
{
    private readonly string _path;
    private readonly JsonSerializerOptions _options = new(JsonSerializerDefaults.Web);

    public JsonlEventWriter(string path)
    {
        _path = path;
    }

    public async Task AppendAsync(CollectorEventEnvelope envelope, CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path) ?? ".");
        var line = JsonSerializer.Serialize(envelope, _options) + Environment.NewLine;
        await File.AppendAllTextAsync(_path, line, cancellationToken);
    }
}
