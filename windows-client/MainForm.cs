using System.Diagnostics;

namespace MinecraftSkinRunPod;

internal sealed class MainForm : Form
{
    private readonly TextBox _promptBox = new();
    private readonly TextBox _imagePathBox = new();
    private readonly NumericUpDown _strengthBox = new();
    private readonly NumericUpDown _stepsBox = new();
    private readonly NumericUpDown _guidanceBox = new();
    private readonly TextBox _seedBox = new();
    private readonly TextBox _negativeBox = new();
    private readonly TextBox _outputPathBox = new();

    private readonly PictureBox _referencePreview = new();
    private readonly PictureBox _outputPreview = new();

    private readonly Label _credentialLabel = new();
    private readonly Label _statusLabel = new();
    private readonly ProgressBar _progress = new();

    private readonly Button _generateButton = new();
    private readonly Button _cancelButton = new();
    private readonly Button _openFolderButton = new();
    private readonly Button _saveAsButton = new();

    private readonly RunPodClient _client = new();

    private AppSettings _settings = SettingsStore.Load();
    private CancellationTokenSource? _generationCancellation;
    private GenerationResult? _lastResult;
    private string? _lastSavedPath;

    public MainForm()
    {
        Text = "Minecraft Skin Generator - RunPod";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(900, 650);
        ClientSize = new Size(1080, 760);
        AutoScaleMode = AutoScaleMode.Dpi;

        BuildUi();
        RefreshCredentialStatus();

        Shown += (_, _) =>
        {
            if (string.IsNullOrWhiteSpace(_settings.EndpointId) ||
                string.IsNullOrWhiteSpace(_settings.ApiKey))
            {
                OpenSettings(firstRun: true);
            }
        };
    }

    private void BuildUi()
    {
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(14),
            ColumnCount = 1,
            RowCount = 3
        };

        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        root.Controls.Add(BuildHeader(), 0, 0);
        root.Controls.Add(BuildBody(), 0, 1);
        root.Controls.Add(BuildFooter(), 0, 2);

        Controls.Add(root);
    }

    private Control BuildHeader()
    {
        var header = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            ColumnCount = 3,
            Margin = new Padding(0, 0, 0, 10)
        };

        header.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        header.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        header.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

        var titlePanel = new FlowLayoutPanel
        {
            AutoSize = true,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            Dock = DockStyle.Fill,
            Margin = Padding.Empty
        };

        titlePanel.Controls.Add(new Label
        {
            Text = "Minecraft Skin Generator",
            AutoSize = true,
            Font = new Font(Font.FontFamily, 17, FontStyle.Bold)
        });

        titlePanel.Controls.Add(new Label
        {
            Text = "Prompt + optional reference image → direct 64×64 Minecraft skin",
            AutoSize = true,
            ForeColor = SystemColors.GrayText,
            Margin = new Padding(0, 3, 0, 0)
        });

        _credentialLabel.AutoSize = true;
        _credentialLabel.Anchor = AnchorStyles.Right;
        _credentialLabel.Margin = new Padding(12, 0, 12, 0);

        var settingsButton = new Button
        {
            Text = "Settings",
            AutoSize = true,
            Anchor = AnchorStyles.Right
        };
        settingsButton.Click += (_, _) => OpenSettings(firstRun: false);

        header.Controls.Add(titlePanel, 0, 0);
        header.Controls.Add(_credentialLabel, 1, 0);
        header.Controls.Add(settingsButton, 2, 0);

        return header;
    }

    private Control BuildBody()
    {
        var split = new SplitContainer
        {
            Dock = DockStyle.Fill,
            Orientation = Orientation.Vertical,
            SplitterDistance = 610,
            Panel1MinSize = 470,
            Panel2MinSize = 280
        };

        split.Panel1.Controls.Add(BuildInputPanel());
        split.Panel2.Controls.Add(BuildPreviewPanel());

        return split;
    }

    private Control BuildInputPanel()
    {
        var scroll = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            Padding = new Padding(0, 0, 10, 0)
        };

        var form = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            ColumnCount = 1,
            Padding = new Padding(4)
        };

        _promptBox.Multiline = true;
        _promptBox.Height = 105;
        _promptBox.Dock = DockStyle.Top;
        _promptBox.ScrollBars = ScrollBars.Vertical;
        _promptBox.PlaceholderText =
            "Example: keep this character's hair, outfit and colors; make a clean Minecraft skin";

        AddField(form, "Prompt", _promptBox,
            "Prompt is optional when you provide a reference image.");

        var imageRow = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            ColumnCount = 2
        };
        imageRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        imageRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

        _imagePathBox.Dock = DockStyle.Fill;
        _imagePathBox.ReadOnly = true;

        var browseImageButton = new Button
        {
            Text = "Choose Image...",
            AutoSize = true,
            Margin = new Padding(8, 0, 0, 0)
        };
        browseImageButton.Click += (_, _) => ChooseReferenceImage();

        imageRow.Controls.Add(_imagePathBox, 0, 0);
        imageRow.Controls.Add(browseImageButton, 1, 0);

        AddField(form, "Reference image", imageRow,
            "PNG/JPG/WebP/GIF, maximum 6 MB.");

        var numbers = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            ColumnCount = 3
        };

        for (var i = 0; i < 3; i++)
        {
            numbers.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.333f));
        }

        ConfigureDecimal(_strengthBox, 0, 1.25m, 0.75m, 2, 0.05m);
        ConfigureInteger(_stepsBox, 10, 60, 35);
        ConfigureDecimal(_guidanceBox, 1, 15, 7.5m, 1, 0.5m);

        numbers.Controls.Add(BuildMiniField("Reference strength", _strengthBox), 0, 0);
        numbers.Controls.Add(BuildMiniField("Steps", _stepsBox), 1, 0);
        numbers.Controls.Add(BuildMiniField("Guidance", _guidanceBox), 2, 0);

        AddField(form, "Generation controls", numbers,
            "0.70–0.80 reference strength is a good starting range.");

        _seedBox.Dock = DockStyle.Top;
        _seedBox.PlaceholderText = "Leave blank for a random seed";
        AddField(form, "Seed (optional)", _seedBox, null);

        _negativeBox.Multiline = true;
        _negativeBox.Height = 65;
        _negativeBox.Dock = DockStyle.Top;
        _negativeBox.ScrollBars = ScrollBars.Vertical;
        _negativeBox.PlaceholderText = "Things the model should avoid";
        AddField(form, "Negative prompt (optional)", _negativeBox, null);

        var outputRow = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            ColumnCount = 2
        };
        outputRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        outputRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

        _outputPathBox.Dock = DockStyle.Fill;
        _outputPathBox.Text = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyPictures),
            "skin.png");

        var browseOutputButton = new Button
        {
            Text = "Browse...",
            AutoSize = true,
            Margin = new Padding(8, 0, 0, 0)
        };
        browseOutputButton.Click += (_, _) => ChooseOutputPath();

        outputRow.Controls.Add(_outputPathBox, 0, 0);
        outputRow.Controls.Add(browseOutputButton, 1, 0);

        AddField(form, "Output PNG", outputRow,
            "The generated skin is saved automatically when the request completes.");

        scroll.Controls.Add(form);
        return scroll;
    }

    private Control BuildPreviewPanel()
    {
        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 2,
            Padding = new Padding(10, 0, 0, 0)
        };

        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 50));

        _referencePreview.Dock = DockStyle.Fill;
        _referencePreview.SizeMode = PictureBoxSizeMode.Zoom;
        _referencePreview.BackColor = Color.FromArgb(28, 28, 30);

        _outputPreview.Dock = DockStyle.Fill;
        _outputPreview.SizeMode = PictureBoxSizeMode.Zoom;
        _outputPreview.BackColor = Color.FromArgb(28, 28, 30);

        layout.Controls.Add(BuildPreviewGroup("Reference Image", _referencePreview), 0, 0);
        layout.Controls.Add(BuildPreviewGroup("Generated 64×64 Skin", _outputPreview), 0, 1);

        return layout;
    }

    private Control BuildFooter()
    {
        var footer = new TableLayoutPanel
        {
            Dock = DockStyle.Bottom,
            AutoSize = true,
            ColumnCount = 2,
            Margin = new Padding(0, 10, 0, 0)
        };

        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

        var statusPanel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            AutoSize = true,
            RowCount = 2
        };

        _statusLabel.Text = "Ready.";
        _statusLabel.AutoSize = true;
        _statusLabel.AutoEllipsis = true;
        _statusLabel.Dock = DockStyle.Fill;

        _progress.Dock = DockStyle.Top;
        _progress.Style = ProgressBarStyle.Marquee;
        _progress.MarqueeAnimationSpeed = 25;
        _progress.Visible = false;
        _progress.Height = 8;

        statusPanel.Controls.Add(_statusLabel, 0, 0);
        statusPanel.Controls.Add(_progress, 0, 1);

        var buttons = new FlowLayoutPanel
        {
            AutoSize = true,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false
        };

        _generateButton.Text = "Generate Skin";
        _generateButton.AutoSize = true;
        _generateButton.Font = new Font(Font, FontStyle.Bold);
        _generateButton.Padding = new Padding(8, 3, 8, 3);
        _generateButton.Click += async (_, _) => await GenerateAsync();

        _cancelButton.Text = "Cancel";
        _cancelButton.AutoSize = true;
        _cancelButton.Enabled = false;
        _cancelButton.Click += (_, _) => _generationCancellation?.Cancel();

        _openFolderButton.Text = "Open Folder";
        _openFolderButton.AutoSize = true;
        _openFolderButton.Enabled = false;
        _openFolderButton.Click += (_, _) => OpenOutputFolder();

        _saveAsButton.Text = "Save As...";
        _saveAsButton.AutoSize = true;
        _saveAsButton.Enabled = false;
        _saveAsButton.Click += (_, _) => SaveLastResultAs();

        buttons.Controls.Add(_generateButton);
        buttons.Controls.Add(_cancelButton);
        buttons.Controls.Add(_openFolderButton);
        buttons.Controls.Add(_saveAsButton);

        footer.Controls.Add(statusPanel, 0, 0);
        footer.Controls.Add(buttons, 1, 0);

        return footer;
    }

    private async Task GenerateAsync()
    {
        if (string.IsNullOrWhiteSpace(_settings.EndpointId) ||
            string.IsNullOrWhiteSpace(_settings.ApiKey))
        {
            OpenSettings(firstRun: false);

            if (string.IsNullOrWhiteSpace(_settings.EndpointId) ||
                string.IsNullOrWhiteSpace(_settings.ApiKey))
            {
                return;
            }
        }

        int? seed = null;
        if (!string.IsNullOrWhiteSpace(_seedBox.Text))
        {
            if (!int.TryParse(_seedBox.Text.Trim(), out var parsedSeed) || parsedSeed < 0)
            {
                MessageBox.Show(this,
                    "Seed must be a whole number between 0 and 2147483647.",
                    "Invalid seed",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                return;
            }

            seed = parsedSeed;
        }

        var options = new GenerationOptions
        {
            Prompt = _promptBox.Text,
            ReferenceImagePath = string.IsNullOrWhiteSpace(_imagePathBox.Text)
                ? null
                : _imagePathBox.Text,
            ReferenceStrength = _strengthBox.Value,
            Steps = decimal.ToInt32(_stepsBox.Value),
            GuidanceScale = _guidanceBox.Value,
            Seed = seed,
            NegativePrompt = _negativeBox.Text
        };

        var outputPath = _outputPathBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(outputPath))
        {
            MessageBox.Show(this, "Choose an output PNG path.", "Missing output",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (!string.Equals(Path.GetExtension(outputPath), ".png",
                StringComparison.OrdinalIgnoreCase))
        {
            outputPath += ".png";
            _outputPathBox.Text = outputPath;
        }

        _generationCancellation?.Dispose();
        _generationCancellation = new CancellationTokenSource();

        SetBusy(true, "Sending request to RunPod...");

        try
        {
            var result = await _client.GenerateAsync(
                _settings,
                options,
                _generationCancellation.Token);

            var fullOutputPath = Path.GetFullPath(outputPath);
            var directory = Path.GetDirectoryName(fullOutputPath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            await File.WriteAllBytesAsync(
                fullOutputPath,
                result.PngBytes,
                _generationCancellation.Token);

            _lastResult = result;
            _lastSavedPath = fullOutputPath;
            SetOutputPreview(result.PngBytes);

            _openFolderButton.Enabled = true;
            _saveAsButton.Enabled = true;

            var details = $"Done - saved {Path.GetFileName(fullOutputPath)}";
            if (result.Width > 0 && result.Height > 0)
            {
                details += $" | {result.Width}×{result.Height}";
            }
            if (result.Seed.HasValue)
            {
                details += $" | Seed {result.Seed.Value}";
            }
            if (!string.IsNullOrWhiteSpace(result.SourceMode))
            {
                details += $" | {result.SourceMode}";
            }

            _statusLabel.Text = details;
        }
        catch (OperationCanceledException)
        {
            _statusLabel.Text = "Cancelled.";
        }
        catch (Exception ex)
        {
            _statusLabel.Text = "Generation failed.";
            MessageBox.Show(
                this,
                ex.Message,
                "RunPod generation failed",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
        finally
        {
            SetBusy(false, preserveStatus: true);
        }
    }

    private void OpenSettings(bool firstRun)
    {
        if (firstRun)
        {
            MessageBox.Show(
                this,
                "Add your RunPod endpoint ID and API key once. The app will keep them in local Windows settings.",
                "RunPod setup",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
        }

        using var dialog = new SettingsDialog(_settings);
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            RefreshCredentialStatus();
            return;
        }

        try
        {
            SettingsStore.Save(dialog.EndpointId, dialog.ApiKey);
            _settings = SettingsStore.Load();
            RefreshCredentialStatus();
            _statusLabel.Text = "Settings saved.";
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "Could not save settings",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void RefreshCredentialStatus()
    {
        if (!string.IsNullOrWhiteSpace(_settings.EndpointId) &&
            !string.IsNullOrWhiteSpace(_settings.ApiKey))
        {
            _credentialLabel.Text = "Endpoint: " + _settings.EndpointId;
            _credentialLabel.ForeColor = Color.DarkGreen;
        }
        else
        {
            _credentialLabel.Text = "RunPod not configured";
            _credentialLabel.ForeColor = Color.Firebrick;
        }
    }

    private void ChooseReferenceImage()
    {
        using var dialog = new OpenFileDialog
        {
            Title = "Choose reference image",
            Filter = "Image files|*.png;*.jpg;*.jpeg;*.webp;*.gif|All files|*.*",
            CheckFileExists = true,
            Multiselect = false
        };

        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        var info = new FileInfo(dialog.FileName);
        if (info.Length > 6L * 1024L * 1024L)
        {
            MessageBox.Show(this,
                "Reference image must be 6 MB or smaller.",
                "Image too large",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
            return;
        }

        _imagePathBox.Text = dialog.FileName;
        SetReferencePreview(dialog.FileName);
    }

    private void ChooseOutputPath()
    {
        using var dialog = new SaveFileDialog
        {
            Title = "Save generated skin",
            Filter = "PNG image|*.png",
            DefaultExt = "png",
            AddExtension = true,
            FileName = Path.GetFileName(_outputPathBox.Text)
        };

        var currentDirectory = Path.GetDirectoryName(_outputPathBox.Text);
        if (!string.IsNullOrWhiteSpace(currentDirectory) &&
            Directory.Exists(currentDirectory))
        {
            dialog.InitialDirectory = currentDirectory;
        }

        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            _outputPathBox.Text = dialog.FileName;
        }
    }

    private void SaveLastResultAs()
    {
        if (_lastResult is null)
        {
            return;
        }

        using var dialog = new SaveFileDialog
        {
            Title = "Save generated Minecraft skin",
            Filter = "PNG image|*.png",
            DefaultExt = "png",
            AddExtension = true,
            FileName = _lastSavedPath is null
                ? "skin.png"
                : Path.GetFileName(_lastSavedPath)
        };

        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        File.WriteAllBytes(dialog.FileName, _lastResult.PngBytes);
        _lastSavedPath = dialog.FileName;
        _outputPathBox.Text = dialog.FileName;
        _openFolderButton.Enabled = true;
        _statusLabel.Text = "Saved: " + dialog.FileName;
    }

    private void OpenOutputFolder()
    {
        if (string.IsNullOrWhiteSpace(_lastSavedPath))
        {
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "explorer.exe",
                Arguments = $"/select,\"{_lastSavedPath}\"",
                UseShellExecute = true
            });
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "Could not open Explorer",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void SetReferencePreview(string path)
    {
        ReplacePicture(_referencePreview, TryLoadImage(path));
    }

    private void SetOutputPreview(byte[] pngBytes)
    {
        try
        {
            using var stream = new MemoryStream(pngBytes);
            using var image = Image.FromStream(stream);
            ReplacePicture(_outputPreview, new Bitmap(image));
        }
        catch
        {
            ReplacePicture(_outputPreview, null);
        }
    }

    private static Image? TryLoadImage(string path)
    {
        try
        {
            using var stream = new FileStream(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite);

            using var image = Image.FromStream(stream);
            return new Bitmap(image);
        }
        catch
        {
            return null;
        }
    }

    private static void ReplacePicture(PictureBox box, Image? next)
    {
        var previous = box.Image;
        box.Image = next;
        previous?.Dispose();
    }

    private void SetBusy(bool busy, string? status = null, bool preserveStatus = false)
    {
        _generateButton.Enabled = !busy;
        _cancelButton.Enabled = busy;
        _progress.Visible = busy;

        if (!preserveStatus && status is not null)
        {
            _statusLabel.Text = status;
        }
        else if (status is not null)
        {
            _statusLabel.Text = status;
        }
    }

    private static void ConfigureDecimal(
        NumericUpDown box,
        decimal minimum,
        decimal maximum,
        decimal value,
        int decimals,
        decimal increment)
    {
        box.Minimum = minimum;
        box.Maximum = maximum;
        box.Value = value;
        box.DecimalPlaces = decimals;
        box.Increment = increment;
        box.Dock = DockStyle.Top;
    }

    private static void ConfigureInteger(
        NumericUpDown box,
        int minimum,
        int maximum,
        int value)
    {
        box.Minimum = minimum;
        box.Maximum = maximum;
        box.Value = value;
        box.DecimalPlaces = 0;
        box.Increment = 1;
        box.Dock = DockStyle.Top;
    }

    private static Control BuildMiniField(string labelText, Control control)
    {
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            RowCount = 2,
            Margin = new Padding(0, 0, 10, 0)
        };

        panel.Controls.Add(new Label
        {
            Text = labelText,
            AutoSize = true,
            Margin = new Padding(0, 0, 0, 5)
        });

        panel.Controls.Add(control);
        return panel;
    }

    private static Control BuildPreviewGroup(string title, PictureBox picture)
    {
        var group = new GroupBox
        {
            Text = title,
            Dock = DockStyle.Fill,
            Padding = new Padding(10)
        };

        group.Controls.Add(picture);
        return group;
    }

    private static void AddField(
        TableLayoutPanel form,
        string labelText,
        Control control,
        string? hint)
    {
        form.RowCount += hint is null ? 2 : 3;

        form.Controls.Add(new Label
        {
            Text = labelText,
            AutoSize = true,
            Font = new Font(SystemFonts.MessageBoxFont, FontStyle.Bold),
            Margin = new Padding(0, 10, 0, 5)
        });

        control.Margin = new Padding(0);
        form.Controls.Add(control);

        if (hint is not null)
        {
            form.Controls.Add(new Label
            {
                Text = hint,
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Margin = new Padding(0, 4, 0, 0)
            });
        }
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _generationCancellation?.Dispose();
            _referencePreview.Image?.Dispose();
            _outputPreview.Image?.Dispose();
        }

        base.Dispose(disposing);
    }
}
