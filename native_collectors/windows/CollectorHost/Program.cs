using Humungousaur.Collectors.Windows.Core;

var options = CollectorHostOptions.Parse(args);
using var cancellation = new CancellationTokenSource();
Console.CancelKeyPress += (_, eventArgs) =>
{
    eventArgs.Cancel = true;
    cancellation.Cancel();
};

await new WindowsCoreOsContextHelper(options).RunAsync(cancellation.Token);
