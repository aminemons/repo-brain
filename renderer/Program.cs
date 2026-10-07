using System.Buffers.Binary;
using System.Numerics;
using System.Text;
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
    private const int MaxOutputPixels = 3_500_000;
    private const int MaxCanvasHeight = 3500;
    private const int CanvasWidth = 1000;

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
                if (png.Length is < 24 or > MaxOutputBytes ||
                    !png.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }))
                {
                    throw new InvalidDataException("Najm produced an invalid or oversized PNG");
                }
                var pngWidth = BinaryPrimitives.ReadUInt32BigEndian(png.AsSpan(16, 4));
                var pngHeight = BinaryPrimitives.ReadUInt32BigEndian(png.AsSpan(20, 4));
                if (pngWidth != CanvasWidth || pngHeight is 0 or > MaxCanvasHeight ||
                    (long)pngWidth * pngHeight > MaxOutputPixels)
                    throw new InvalidDataException("Najm produced an image outside the canvas bounds");
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
        private static readonly Color Edge = new(0.35f, 0.5f, 0.67f);
        private static readonly Color Accent = new(0.38f, 0.78f, 0.95f);
        private const float SidePadding = 56;
        private const float CardGap = 34;
        private readonly Typesetter typesetter;

        public GraphScene(GraphRequest graph, Typesetter typesetter)
        {
            this.typesetter = typesetter;
            // Keep maps of three or fewer sources in one reading column; larger maps use two
            // columns while keeping node labels inside the bounded phone-width canvas. Height
            // follows the number and measured content of the nodes.
            var edgeGutter = graph.Edges.Length == 0 ? 0 : 24 + (graph.Edges.Length * 8);
            var cardX = SidePadding + edgeGutter;
            var columns = graph.Nodes.Length > 3 ? 2 : 1;
            var availableWidth = Program.CanvasWidth - cardX - SidePadding;
            var cardWidth = columns == 1 ? availableWidth : (availableWidth - CardGap) / 2;
            var textWidth = cardWidth - 48;
            var title = WrappedLayout(graph.Title, Program.CanvasWidth - (SidePadding * 2), 42);
            var cards = graph.Nodes.Select(node => MakeCard(node, graph.Edges, textWidth)).ToArray();
            var contentTop = 58 + title.LogicalBounds.Height + 56;
            var rowHeights = cards.Chunk(columns).Select(row => row.Max(card => card.Height)).ToArray();
            var imageHeight = contentTop + rowHeights.Sum(height => height + CardGap) - CardGap + 40;
            if (!float.IsFinite(imageHeight) || imageHeight > MaxCanvasHeight ||
                Program.CanvasWidth * imageHeight > MaxOutputPixels)
                throw new InvalidDataException("the graph exceeds the renderer's bounded canvas");
            VirtualResolution = new Vector2(CanvasWidth, Math.Max(220, imageHeight));
            var layer = Layers.Add(new ScreenLayer { ClearColor = Background });

            layer.Root.Add(new TextNode(title, new Vector2(SidePadding, 58), Accent,
                Program.CanvasWidth - (SidePadding * 2), title.LogicalBounds.Height + 8));

            var cardById = new Dictionary<string, CardLayout>(StringComparer.Ordinal);
            var rowY = contentTop;
            for (var row = 0; row < rowHeights.Length; row++)
            {
                for (var column = 0; column < columns; column++)
                {
                    var index = (row * columns) + column;
                    if (index >= cards.Length) break;
                    var card = cards[index];
                    card.Position = new Vector2(cardX + (column * (cardWidth + CardGap)), rowY);
                    cardById.Add(card.Node.Id, card);
                }
                rowY += rowHeights[row] + CardGap;
            }

            for (var index = 0; index < graph.Edges.Length; index++)
            {
                var edge = graph.Edges[index];
                if (edge.Source == edge.Target) continue;
                if (columns == 1)
                {
                    layer.Root.Add(new RoutedEdgeNode(
                        new Vector2(cardX, cardById[edge.Source].Position.Y + (cardById[edge.Source].Height * 0.5f)),
                        new Vector2(cardX, cardById[edge.Target].Position.Y + (cardById[edge.Target].Height * 0.5f)),
                        cardX, 24 + (index * 8), Edge));
                }
                else
                {
                    var source = cardById[edge.Source];
                    var target = cardById[edge.Target];
                    layer.Root.Add(new DirectEdgeNode(
                        source.Position + new Vector2(cardWidth * 0.5f, source.Height * 0.5f),
                        target.Position + new Vector2(cardWidth * 0.5f, target.Height * 0.5f), Edge));
                }
            }

            foreach (var card in cards)
                AddCard(layer.Root, card, cardWidth);
        }

        private ITextLayout Typeset(string text, float size) =>
            typesetter.Typeset(new TypesetRequest(text, new Style { Size = size }));

        private ITextLayout WrappedLayout(string text, float width, float size) =>
            Typeset(string.Join('\n', WrapText(text, width, size)), size);

        private string[] WrapText(string text, float width, float size)
        {
            var words = text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return ["(empty)"];
            var lines = new List<string>();
            var current = "";
            foreach (var word in words)
            {
                IEnumerable<string> pieces = Measure(word, size) <= width ? new[] { word } : SplitLongWord(word, width, size);
                foreach (var piece in pieces)
                {
                    var candidate = current.Length == 0 ? piece : $"{current} {piece}";
                    if (current.Length > 0 && Measure(candidate, size) > width)
                    {
                        lines.Add(current);
                        current = piece;
                    }
                    else
                    {
                        current = candidate;
                    }
                }
            }
            if (current.Length > 0) lines.Add(current);
            return [.. lines];
        }

        private List<string> SplitLongWord(string word, float width, float size)
        {
            var pieces = new List<string>();
            var current = "";
            foreach (var rune in word.EnumerateRunes())
            {
                var candidate = current + rune.ToString();
                if (current.Length > 0 && Measure(candidate, size) > width)
                {
                    pieces.Add(current);
                    current = rune.ToString();
                }
                else
                {
                    current = candidate;
                }
            }
            if (current.Length > 0) pieces.Add(current);
            return pieces;
        }

        private float Measure(string text, float size) => Typeset(text, size).LogicalBounds.Width;

        private CardLayout MakeCard(GraphNode node, GraphEdge[] edges, float textWidth)
        {
            const float padding = 24;
            var id = Typeset(node.Id, 22);
            var label = WrappedLayout(node.Label, textWidth, 34);
            var source = WrappedLayout(node.SourceRef, textWidth, 21);
            var relations = edges.Where(edge => edge.Source == node.Id)
                .Select(edge => WrappedLayout($"{edge.Label} -> {edge.Target}", textWidth, 20))
                .ToArray();
            var idY = 22;
            var labelY = idY + id.LogicalBounds.Height + 18;
            var sourceY = labelY + label.LogicalBounds.Height + 16;
            var relationsY = sourceY + source.LogicalBounds.Height + 18;
            var relationHeight = relations.Sum(relation => relation.LogicalBounds.Height + 5);
            var height = Math.Max(220, relationsY + relationHeight + padding);
            return new CardLayout(node, id, label, source, relations, idY, labelY, sourceY,
                relationsY, height);
        }

        private static void AddCard(Node2D nodes, CardLayout card, float cardWidth)
        {
            nodes.Add(new CardNode(card.Position, cardWidth, card.Height, Card, Accent));
            var left = card.Position + new Vector2(24, 0);
            nodes.Add(new TextNode(card.Id, left + new Vector2(0, card.IdY), Accent,
                cardWidth - 48, card.Id.LogicalBounds.Height + 4));
            nodes.Add(new TextNode(card.Label, left + new Vector2(0, card.LabelY), Color.White,
                cardWidth - 48, card.Label.LogicalBounds.Height + 6));
            nodes.Add(new TextNode(card.Source, left + new Vector2(0, card.SourceY),
                new Color(0.72f, 0.79f, 0.88f), cardWidth - 48,
                card.Source.LogicalBounds.Height + 6));
            var relationY = card.RelationsY;
            foreach (var relation in card.Relations)
            {
                nodes.Add(new TextNode(relation, left + new Vector2(0, relationY), Accent,
                    cardWidth - 48, relation.LogicalBounds.Height + 4));
                relationY += relation.LogicalBounds.Height + 5;
            }
        }

        private sealed class CardLayout(
            GraphNode node,
            ITextLayout id,
            ITextLayout label,
            ITextLayout source,
            ITextLayout[] relations,
            float idY,
            float labelY,
            float sourceY,
            float relationsY,
            float height)
        {
            public GraphNode Node { get; } = node;
            public ITextLayout Id { get; } = id;
            public ITextLayout Label { get; } = label;
            public ITextLayout Source { get; } = source;
            public ITextLayout[] Relations { get; } = relations;
            public float IdY { get; } = idY;
            public float LabelY { get; } = labelY;
            public float SourceY { get; } = sourceY;
            public float RelationsY { get; } = relationsY;
            public float Height { get; } = height;
            public Vector2 Position { get; set; }
        }
    }

    private sealed class CardNode : Drawable
    {
        private readonly Color cardColor;
        private readonly Color accentColor;

        private readonly float width;
        private readonly float height;

        public CardNode(Vector2 position, float width, float height, Color cardColor, Color accentColor)
        {
            Position = position;
            this.width = width;
            this.height = height;
            this.cardColor = cardColor;
            this.accentColor = accentColor;
        }

        public override Rect VisualBounds => new(0, 0, width, height);

        public override void Render(IDrawContext2D context)
        {
            var corners = new Vector2(15, 15);
            context.DrawRoundRect(new Rect(0, 0, width, height), corners, Paint.Fill(cardColor));
            context.DrawRoundRect(new Rect(0, 0, width, height), corners,
                Paint.Stroke(accentColor.WithAlpha(0.55f), 1.5f));
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

    private sealed class RoutedEdgeNode(
        Vector2 source,
        Vector2 target,
        float cardX,
        float laneX,
        Color color) : Drawable
    {
        public override Rect VisualBounds =>
            new(0, 0, Program.CanvasWidth, Math.Max(source.Y, target.Y) + 12);

        public override void Render(IDrawContext2D context)
        {
            var paint = Paint.Stroke(color.WithAlpha(0.88f), 2.5f);
            var from = new Vector2(cardX, source.Y);
            var laneFrom = new Vector2(laneX, source.Y);
            var laneTo = new Vector2(laneX, target.Y);
            var to = new Vector2(cardX - 8, target.Y);
            context.DrawLine(from, laneFrom, paint);
            context.DrawLine(laneFrom, laneTo, paint);
            context.DrawLine(laneTo, to, paint);
            context.DrawLine(new Vector2(cardX - 15, target.Y - 7), to, paint);
            context.DrawLine(new Vector2(cardX - 15, target.Y + 7), to, paint);
        }
    }

    private sealed class DirectEdgeNode(Vector2 source, Vector2 target, Color color) : Drawable
    {
        public override Rect VisualBounds =>
            new(0, 0, Program.CanvasWidth, Math.Max(source.Y, target.Y) + 12);

        public override void Render(IDrawContext2D context) =>
            context.DrawLine(source, target, Paint.Stroke(color.WithAlpha(0.55f), 2));
    }
}
