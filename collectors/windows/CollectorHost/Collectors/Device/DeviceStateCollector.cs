using System.Net.NetworkInformation;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Device;

internal sealed class DeviceStateCollector
{
    private bool? _networkAvailable;
    private bool? _chargerConnected;
    private bool _batteryLow;
    private bool? _idle;

    public IEnumerable<CollectorHostEvent> Diff()
    {
        var network = NetworkInterface.GetIsNetworkAvailable();
        if (_networkAvailable is not null && network != _networkAvailable)
        {
            yield return Create("network_changed", "Network availability changed.", new Dictionary<string, string> { ["network_available"] = network.ToString().ToLowerInvariant() });
        }
        _networkAvailable = network;

        if (NativeMethods.GetSystemPowerStatus(out var power))
        {
            var charging = power.AcLineStatus == 1;
            if (_chargerConnected is not null && charging && charging != _chargerConnected)
            {
                yield return Create("charger_connected", "Charger connected.", new Dictionary<string, string> { ["charging"] = "true", ["battery_percent"] = power.BatteryLifePercent.ToStringInvariant() });
            }
            _chargerConnected = charging;

            var batteryLow = power.BatteryLifePercent <= 15 && power.BatteryLifePercent <= 100;
            if (batteryLow && !_batteryLow)
            {
                yield return Create("battery_low", "Battery low.", new Dictionary<string, string> { ["battery_percent"] = power.BatteryLifePercent.ToStringInvariant() });
            }
            _batteryLow = batteryLow;
        }

        var idleSeconds = NativeMethods.IdleSeconds();
        var idle = idleSeconds >= 60;
        if (_idle is not null && idle != _idle)
        {
            yield return Create(
                "user_idle_state_changed",
                idle ? "User became idle." : "User became active.",
                new Dictionary<string, string> { ["idle"] = idle.ToString().ToLowerInvariant(), ["idle_seconds_bucket"] = BucketSeconds(idleSeconds) }
            );
        }
        _idle = idle;
    }

    private static CollectorHostEvent Create(string stimulusType, string text, Dictionary<string, string> metadata) =>
        new(CollectorCatalog.DeviceState, "system", stimulusType, text, metadata);

    private static string BucketSeconds(uint seconds) => seconds switch
    {
        < 60 => "under_60",
        < 300 => "60_299",
        < 900 => "300_899",
        _ => "900_plus",
    };
}
