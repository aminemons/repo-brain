using System.Numerics;
using System.Text.Json.Serialization;
using System.Text.Json;
using Najm.Core;
using Najm.Core.Text;
using Najm.Skia;
using Najm.Text;
using Najm.Utils;

namespace RepoBrainNajmRenderer;

internal static class Program
{
    private const int MaxInputBytes = 32 * 1024;
    private const int MaxOutputBytes = 8 * 1024 * 1024;

    public static int Main()
    {
        try
        {
            using var input = new MemoryStream();
            var buffer = new byte[4096];
            int count;
            while ((count = Console.OpenStandardInput().Read(buffer, 0, buffer.Length)) > 0)
            {
                if (input.Length + count > MaxInputBytes)
                {
                    Console.Error.WriteLine("input exceeds the 32 KiB limit");
                    return 2;
                }
                input.Write(buffer, 0, count);
            }

            var graph = JsonSerializer.Deserialize<GraphRequest>(input.ToArray(), JsonOptions)
                ?? throw new InvalidDataException("request JSON must be an object");
            Validate(graph);

            using var typesetter = new Typesetter();
            var scene = new GraphScene(graph, typesetter);
            var path = Path.Combine(Path.GetTempPath(), $"repobrain-{Guid.NewGuid():N}.png");
            try
            {
                SkiaExport.Png(() => scene, path, at: 0, typesetter: typesetter);
                var png = File.ReadAllBytes(path);
                if (png.Length is < 8 or > MaxOutputBytes ||
                    !png.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }))
                {
                    throw new InvalidDataException("Najm produced an invalid or oversized PNG");
                }
                Console.OpenStandardOutput().Write(png);
                return 0;
            }
            finally
            {
                File.Delete(path);
            }
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine($"render failed: {exception.Message}");
            return 1;
        }
    }

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = false,
        MaxDepth = 12,
    };

    private static void Validate(GraphRequest graph)
    {
        if (graph.Version != 1 || string.IsNullOrWhiteSpace(graph.Title) || graph.Title.Length > 120)
            throw new InvalidDataException("version must be 1 and title must contain 1–120 characters");
        if (graph.Nodes is null || graph.Nodes.Length > 6 || graph.Edges is null || graph.Edges.Length > 12)
            throw new InvalidDataException("at most 6 nodes and 12 edges are allowed");

        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var node in graph.Nodes)
        {
            if (node.Id is null || node.Label is null || node.SourceRef is null ||
                !System.Text.RegularExpressions.Regex.IsMatch(node.Id, "^S[1-6]$") ||
                node.Label.Length > 80 || node.SourceRef.Length > 160 ||
                !ids.Add(node.Id))
                throw new InvalidDataException("node fields must use unique S1–S6 IDs and bounded strings");
        }

        foreach (var edge in graph.Edges)
        {
            if (edge.Source is null || edge.Target is null || edge.Label is null ||
                !ids.Contains(edge.Source) || !ids.Contains(edge.Target) || edge.Label.Length > 80)
                throw new InvalidDataException("edge endpoints must reference nodes and labels are limited to 80 characters");
        }
    }

    private sealed record GraphRequest(int Version, string Title, GraphNode[] Nodes, GraphEdge[] Edges);
    private sealed record GraphNode(
        string Id,
        string Label,
        [property: JsonPropertyName("source_ref")] string SourceRef);
    private sealed record GraphEdge(string Source, string Target, string Label);

    private sealed class GraphScene : Scene
    {
        private static readonly Color Background = new(0.035f, 0.055f, 0.09f);
        private static readonly Color Card = new(0.075f, 0.105f, 0.16f);
        private static readonly Color Edge = new(0.3f, 0.43f, 0.58f);
        private static readonly Color Accent = new(0.38f, 0.78f, 0.95f);
        private readonly Typesetter typesetter;

        public GraphScene(GraphRequest graph, Typesetter typesetter)
        {
            this.typesetter = typesetter;
            VirtualResolution = new Vector2(1400, 1000);
            var layer = Layers.Add(new ScreenLayer { ClearColor = Background });

            var titleLayout = Typeset(string.Join('\n', BreakText(graph.Title, 60)), 34);
            layer.Root.Add(new TextNode(titleLayout, new Vector2(56, 88), Accent, 1200, 100));

            var positions = new Dictionary<string, Vector2>(StringComparer.Ordinal);
            for (var i = 0; i < graph.Nodes.Length; i++)
            {
                var column = i % 3;
                var row = i / 3;
                var position = new Vector2(56 + (column * 440), 190 + (row * 380));
                positions.Add(graph.Nodes[i].Id, position);
            }

            foreach (var edge in graph.Edges)
            {
                var start = positions[edge.Source] + new Vector2(195, 167);
                var end = positions[edge.Target] + new Vector2(195, 167);
                layer.Root.Add(new EdgeNode(
                    start,
                    end,
                    Edge));
                var midpoint = (start + end) * 0.5f;
                layer.Root.Add(new TextNode(Typeset(edge.Label, 15), midpoint + new Vector2(8, -8), Color.White, 340, 30));
            }

            foreach (var node in graph.Nodes)
            {
                var lines = BreakText(node.Label, 28);
                var reference = BreakText(node.SourceRef, 34);
                var label = Typeset(string.Join('\n', lines), 23);
                var source = Typeset(string.Join('\n', reference), 14);
                layer.Root.Add(new CardNode(positions[node.Id], Card, Accent));
                layer.Root.Add(new TextNode(Typeset(node.Id, 18), positions[node.Id] + new Vector2(22, 38), Accent, 70, 30));
                layer.Root.Add(new TextNode(label, positions[node.Id] + new Vector2(22, 94), Color.White, 350, 110));
                layer.Root.Add(new TextNode(source, positions[node.Id] + new Vector2(22, 210), new Color(0.63f, 0.7f, 0.79f), 350, 110));
            }
        }

        private ITextLayout Typeset(string text, float size) =>
            typesetter.Typeset(new TypesetRequest(text, new Style { Size = size }));

        private static string[] BreakText(string text, int width)
        {
            if (text.Length == 0) return ["(empty)"];
            var lines = new List<string>();
            for (var offset = 0; offset < text.Length; offset += width)
                lines.Add(text.Substring(offset, Math.Min(width, text.Length - offset)));
            return [.. lines];
        }
    }

    private sealed class CardNode : Drawable
    {
        private readonly Color cardColor;
        private readonly Color accentColor;

        public CardNode(Vector2 position, Color cardColor, Color accentColor)
        {
            Position = position;
            this.cardColor = cardColor;
            this.accentColor = accentColor;
        }

        public override Rect VisualBounds => new(0, 0, 390, 335);

        public override void Render(IDrawContext2D context)
        {
            var corners = new Vector2(15, 15);
            context.DrawRoundRect(new Rect(0, 0, 390, 335), corners, Paint.Fill(cardColor));
            context.DrawRoundRect(new Rect(0, 0, 390, 335), corners, Paint.Stroke(accentColor.WithAlpha(0.55f), 1.5f));
        }
    }

    private sealed class TextNode : Drawable
    {
        private readonly ITextLayout layout;
        private readonly Color color;
        private readonly Rect bounds;

        public TextNode(ITextLayout layout, Vector2 position, Color color, float width, float height)
        {
            this.layout = layout;
            this.color = color;
            Position = position;
            bounds = new Rect(0, 0, width, height);
        }

        public override Rect VisualBounds => bounds;

        public override void Render(IDrawContext2D context) => context.DrawText(layout, color);
    }

    private sealed class EdgeNode(
        Vector2 source,
        Vector2 target,
        Color color) : Drawable
    {
        public override Rect VisualBounds => new(0, 0, 1400, 1000);

        public override void Render(IDrawContext2D context)
        {
            context.DrawLine(source, target, Paint.Stroke(color.WithAlpha(0.8f), 2));
        }
    }
}
