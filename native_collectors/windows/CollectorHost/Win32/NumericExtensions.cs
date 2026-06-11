namespace Humungousaur.Collectors.Windows.Win32;

internal static class NumericExtensions
{
    public static string ToStringInvariant(this int value) => value.ToString(System.Globalization.CultureInfo.InvariantCulture);
    public static string ToStringInvariant(this uint value) => value.ToString(System.Globalization.CultureInfo.InvariantCulture);
    public static string ToStringInvariant(this byte value) => value.ToString(System.Globalization.CultureInfo.InvariantCulture);
}
