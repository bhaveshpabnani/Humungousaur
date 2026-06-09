using Microsoft.UI.Text;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Documents;
using Microsoft.UI.Xaml.Media;

namespace Humungousaur.App;

public sealed class MarkdownTextBlock : RichTextBlock
{
    public static readonly DependencyProperty MarkdownProperty = DependencyProperty.Register(
        nameof(Markdown),
        typeof(string),
        typeof(MarkdownTextBlock),
        new PropertyMetadata("", OnMarkdownChanged));

    public string Markdown
    {
        get => (string)GetValue(MarkdownProperty);
        set => SetValue(MarkdownProperty, value);
    }

    public MarkdownTextBlock()
    {
        IsTextSelectionEnabled = true;
        TextWrapping = TextWrapping.WrapWholeWords;
    }

    private static void OnMarkdownChanged(DependencyObject dependencyObject, DependencyPropertyChangedEventArgs args)
    {
        if (dependencyObject is MarkdownTextBlock block)
        {
            block.RenderMarkdown(args.NewValue as string ?? "");
        }
    }

    private void RenderMarkdown(string markdown)
    {
        Blocks.Clear();
        var lines = markdown.Replace("\r\n", "\n").Split('\n');
        foreach (var rawLine in lines)
        {
            var line = rawLine.TrimEnd();
            if (line.Length == 0)
            {
                Blocks.Add(new Paragraph());
                continue;
            }

            var paragraph = new Paragraph();
            var content = line.TrimStart();
            if (content.StartsWith("### ", StringComparison.Ordinal))
            {
                paragraph.FontWeight = FontWeights.SemiBold;
                paragraph.FontSize = 15;
                AppendInline(paragraph, content[4..]);
            }
            else if (content.StartsWith("## ", StringComparison.Ordinal))
            {
                paragraph.FontWeight = FontWeights.SemiBold;
                paragraph.FontSize = 17;
                AppendInline(paragraph, content[3..]);
            }
            else if (content.StartsWith("# ", StringComparison.Ordinal))
            {
                paragraph.FontWeight = FontWeights.SemiBold;
                paragraph.FontSize = 20;
                AppendInline(paragraph, content[2..]);
            }
            else if (content.StartsWith("- ", StringComparison.Ordinal) || content.StartsWith("* ", StringComparison.Ordinal))
            {
                paragraph.Inlines.Add(new Run { Text = "• " });
                AppendInline(paragraph, content[2..]);
            }
            else
            {
                AppendInline(paragraph, line);
            }
            Blocks.Add(paragraph);
        }
    }

    private static void AppendInline(Paragraph paragraph, string text)
    {
        var cursor = 0;
        while (cursor < text.Length)
        {
            var bold = text.IndexOf("**", cursor, StringComparison.Ordinal);
            var code = text.IndexOf('`', cursor);
            var next = NextMarker(bold, code);
            if (next < 0)
            {
                paragraph.Inlines.Add(new Run { Text = text[cursor..] });
                return;
            }
            if (next > cursor)
            {
                paragraph.Inlines.Add(new Run { Text = text[cursor..next] });
            }
            if (next == bold)
            {
                var end = text.IndexOf("**", next + 2, StringComparison.Ordinal);
                if (end < 0)
                {
                    paragraph.Inlines.Add(new Run { Text = text[next..] });
                    return;
                }
                paragraph.Inlines.Add(new Run { Text = text[(next + 2)..end], FontWeight = FontWeights.SemiBold });
                cursor = end + 2;
                continue;
            }
            var codeEnd = text.IndexOf('`', next + 1);
            if (codeEnd < 0)
            {
                paragraph.Inlines.Add(new Run { Text = text[next..] });
                return;
            }
            paragraph.Inlines.Add(new Run { Text = text[(next + 1)..codeEnd], FontFamily = new FontFamily("Consolas") });
            cursor = codeEnd + 1;
        }
    }

    private static int NextMarker(int left, int right)
    {
        if (left < 0)
        {
            return right;
        }
        if (right < 0)
        {
            return left;
        }
        return Math.Min(left, right);
    }
}
