// Zero-install Windows RunPod client for Command Prompt.
// Uses built-in Windows Script Host (cscript.exe), WinHTTP, MSXML and ADODB.

(function () {
    function fail(message, code) {
        WScript.Echo("ERROR: " + message);
        WScript.Quit(code || 1);
    }

    function usage() {
        WScript.Echo("Minecraft Skin RunPod Client (Command Prompt)");
        WScript.Echo("");
        WScript.Echo("Environment variables:");
        WScript.Echo("  RUNPOD_API_KEY       Your RunPod API key");
        WScript.Echo("  RUNPOD_ENDPOINT_ID   Your RunPod endpoint ID");
        WScript.Echo("");
        WScript.Echo("Examples:");
        WScript.Echo('  runpod-client.cmd --prompt "white fox girl, blue eyes" --output skin.png');
        WScript.Echo('  runpod-client.cmd --image "C:\\Pictures\\character.png" --output skin.png');
        WScript.Echo('  runpod-client.cmd --prompt "keep outfit and colors" --image "C:\\Pictures\\character.png" --strength 0.75 --output skin.png');
        WScript.Echo("");
        WScript.Echo("Options:");
        WScript.Echo("  --prompt TEXT");
        WScript.Echo("  --image PATH");
        WScript.Echo("  --strength NUMBER       Default: 0.70");
        WScript.Echo("  --steps NUMBER          Default: 35");
        WScript.Echo("  --guidance NUMBER       Default: 7.5");
        WScript.Echo("  --seed NUMBER");
        WScript.Echo("  --output PATH           Default: skin.png");
        WScript.Echo("  --format modern|legacy  Default: modern");
        WScript.Echo("  --negative TEXT");
        WScript.Echo("  --help");
    }

    function getEnv(name) {
        var shell = new ActiveXObject("WScript.Shell");
        var env = shell.Environment("PROCESS");
        return String(env(name) || "");
    }

    function parseArgs() {
        var args = WScript.Arguments;
        var opts = {
            prompt: "",
            image: "",
            strength: 0.70,
            steps: 35,
            guidance: 7.5,
            seed: null,
            output: "skin.png",
            format: "modern",
            negative: ""
        };

        for (var i = 0; i < args.length; i++) {
            var key = String(args(i));
            if (key === "--help" || key === "-h") {
                usage();
                WScript.Quit(0);
            }
            if (i + 1 >= args.length) {
                fail("Missing value for " + key);
            }
            var value = String(args(++i));
            switch (key) {
                case "--prompt": opts.prompt = value; break;
                case "--image": opts.image = value; break;
                case "--strength":
                case "--reference-strength": opts.strength = parseFloat(value); break;
                case "--steps": opts.steps = parseInt(value, 10); break;
                case "--guidance": opts.guidance = parseFloat(value); break;
                case "--seed": opts.seed = parseInt(value, 10); break;
                case "--output": opts.output = value; break;
                case "--format": opts.format = value; break;
                case "--negative": opts.negative = value; break;
                default: fail("Unknown option: " + key);
            }
        }
        return opts;
    }

    function readBinary(path) {
        var stream = new ActiveXObject("ADODB.Stream");
        stream.Type = 1; // binary
        stream.Open();
        stream.LoadFromFile(path);
        var bytes = stream.Read();
        stream.Close();
        return bytes;
    }

    function bytesToBase64(bytes) {
        var doc = new ActiveXObject("Msxml2.DOMDocument.6.0");
        var node = doc.createElement("base64");
        node.dataType = "bin.base64";
        node.nodeTypedValue = bytes;
        return String(node.text).replace(/[\r\n\t ]/g, "");
    }

    function base64ToBytes(text) {
        var doc = new ActiveXObject("Msxml2.DOMDocument.6.0");
        var node = doc.createElement("base64");
        node.dataType = "bin.base64";
        node.text = text;
        return node.nodeTypedValue;
    }

    function saveBinary(path, bytes) {
        var stream = new ActiveXObject("ADODB.Stream");
        stream.Type = 1;
        stream.Open();
        stream.Write(bytes);
        stream.SaveToFile(path, 2); // overwrite
        stream.Close();
    }

    function jsonEscape(s) {
        return String(s)
            .replace(/\\/g, "\\\\")
            .replace(/\"/g, '\\"')
            .replace(/\r/g, "\\r")
            .replace(/\n/g, "\\n")
            .replace(/\t/g, "\\t");
    }

    function jsonString(s) {
        return '"' + jsonEscape(s) + '"';
    }

    function buildJson(input) {
        var parts = [];
        parts.push('"prompt":' + jsonString(input.prompt));
        parts.push('"steps":' + input.steps);
        parts.push('"guidance_scale":' + input.guidance);
        parts.push('"format":' + jsonString(input.format));

        if (input.negative) {
            parts.push('"negative_prompt":' + jsonString(input.negative));
        }
        if (input.imageBase64) {
            parts.push('"reference_image_base64":' + jsonString(input.imageBase64));
            parts.push('"reference_strength":' + input.strength);
        }
        if (input.seed !== null && !isNaN(input.seed)) {
            parts.push('"seed":' + input.seed);
        }
        return '{"input":{' + parts.join(",") + '}}';
    }

    function parseJson(text) {
        if (typeof JSON !== "undefined" && JSON.parse) {
            return JSON.parse(text);
        }
        return eval("(" + text + ")");
    }

    var opts = parseArgs();
    var endpointId = getEnv("RUNPOD_ENDPOINT_ID");
    var apiKey = getEnv("RUNPOD_API_KEY");

    if (!endpointId) fail("RUNPOD_ENDPOINT_ID is not set. Example: set RUNPOD_ENDPOINT_ID=your_endpoint_id");
    if (!apiKey) fail("RUNPOD_API_KEY is not set. Example: set RUNPOD_API_KEY=your_api_key");
    if (!opts.prompt && !opts.image) fail("Provide --prompt, --image, or both.");
    if (opts.format !== "modern" && opts.format !== "legacy") fail("--format must be modern or legacy.");
    if (isNaN(opts.strength) || opts.strength < 0 || opts.strength > 2) fail("--strength must be a valid number between 0 and 2.");
    if (isNaN(opts.steps) || opts.steps < 10 || opts.steps > 60) fail("--steps must be between 10 and 60.");

    var fso = new ActiveXObject("Scripting.FileSystemObject");
    var imageBase64 = "";
    if (opts.image) {
        if (!fso.FileExists(opts.image)) fail("Image not found: " + opts.image);
        var file = fso.GetFile(opts.image);
        if (file.Size > 6 * 1024 * 1024) fail("Reference image must be 6 MB or smaller.");
        WScript.Echo("Encoding reference image...");
        imageBase64 = bytesToBase64(readBinary(file.Path));
    }

    opts.imageBase64 = imageBase64;
    var body = buildJson(opts);
    var url = "https://api.runpod.ai/v2/" + endpointId + "/runsync?wait=300000";

    WScript.Echo("Sending request to RunPod...");
    var http = new ActiveXObject("WinHttp.WinHttpRequest.5.1");
    http.SetTimeouts(30000, 30000, 30000, 330000);
    http.Open("POST", url, false);
    http.SetRequestHeader("Authorization", "Bearer " + apiKey);
    http.SetRequestHeader("Content-Type", "application/json");
    http.Send(body);

    if (http.Status < 200 || http.Status >= 300) {
        fail("RunPod HTTP " + http.Status + ": " + http.ResponseText);
    }

    var responseText = String(http.ResponseText);
    var result;
    try {
        result = parseJson(responseText);
    } catch (e) {
        fail("Could not parse RunPod response: " + responseText);
    }

    if (String(result.status || "") !== "COMPLETED") {
        WScript.Echo(responseText);
        fail("RunPod job did not complete successfully. Status: " + String(result.status || "unknown"));
    }
    if (!result.output || !result.output.image_base64) {
        WScript.Echo(responseText);
        fail("RunPod response does not contain output.image_base64.");
    }

    var outputPath = fso.GetAbsolutePathName(opts.output);
    saveBinary(outputPath, base64ToBytes(String(result.output.image_base64)));

    WScript.Echo("Saved: " + outputPath);
    if (result.output.width && result.output.height) {
        WScript.Echo("Size: " + result.output.width + "x" + result.output.height);
    }
    if (result.output.seed !== undefined) {
        WScript.Echo("Seed: " + result.output.seed);
    }
    if (result.output.source_mode) {
        WScript.Echo("Mode: " + result.output.source_mode);
    }
})();
