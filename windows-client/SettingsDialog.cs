namespace MinecraftSkinRunPod;

internal sealed class SettingsDialog : Form
{
    private readonly TextBox _endpointBox = new();
    private readonly TextBox _apiKeyBox = new();

    public string EndpointId => _endpointBox.Text.Trim();
    public string ApiKey => _apiKeyBox.Text.Trim();

    public SettingsDialog(AppSettings current)
    {
        Text = "RunPod Settings";
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ShowInTaskbar = false;
        ClientSize = new Size(560, 245);
        AutoScaleMode = AutoScaleMode.Dpi;

        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(18),
            ColumnCount = 1,
            RowCount = 7
        };

        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        var intro = new Label
        {
            AutoSize = true,
            MaximumSize = new Size(510, 0),
            Text = "These credentials are saved only on this Windows account. " +
                   "The API key is encrypted with Windows DPAPI and is never stored in the GitHub repository."
        };

        var endpointLabel = new Label
        {
            AutoSize = true,
            Text = "RunPod Endpoint ID",
            Margin = new Padding(0, 14, 0, 5)
        };

        _endpointBox.Dock = DockStyle.Top;
        _endpointBox.Text = current.EndpointId;

        var apiLabel = new Label
        {
            AutoSize = true,
            Text = "RunPod API Key",
            Margin = new Padding(0, 12, 0, 5)
        };

        _apiKeyBox.Dock = DockStyle.Top;
        _apiKeyBox.UseSystemPasswordChar = true;
        _apiKeyBox.Text = current.ApiKey;

        var location = new Label
        {
            AutoSize = true,
            ForeColor = SystemColors.GrayText,
            MaximumSize = new Size(510, 0),
            Text = "Settings file: " + SettingsStore.Location,
            Margin = new Padding(0, 9, 0, 0)
        };

        var buttons = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            AutoSize = true,
            FlowDirection = FlowDirection.RightToLeft,
            WrapContents = false
        };

        var saveButton = new Button
        {
            Text = "Save",
            AutoSize = true,
            DialogResult = DialogResult.None
        };

        var cancelButton = new Button
        {
            Text = "Cancel",
            AutoSize = true,
            DialogResult = DialogResult.Cancel
        };

        saveButton.Click += (_, _) =>
        {
            if (string.IsNullOrWhiteSpace(EndpointId))
            {
                MessageBox.Show(this, "Enter your RunPod endpoint ID.", "Missing endpoint",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                _endpointBox.Focus();
                return;
            }

            if (string.IsNullOrWhiteSpace(ApiKey))
            {
                MessageBox.Show(this, "Enter your RunPod API key.", "Missing API key",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                _apiKeyBox.Focus();
                return;
            }

            DialogResult = DialogResult.OK;
            Close();
        };

        buttons.Controls.Add(saveButton);
        buttons.Controls.Add(cancelButton);

        root.Controls.Add(intro);
        root.Controls.Add(endpointLabel);
        root.Controls.Add(_endpointBox);
        root.Controls.Add(apiLabel);
        root.Controls.Add(_apiKeyBox);
        root.Controls.Add(location);
        root.Controls.Add(buttons);

        Controls.Add(root);

        AcceptButton = saveButton;
        CancelButton = cancelButton;
    }
}
