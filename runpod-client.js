// Zero-install Windows RunPod client.
// - Double-click runpod-client.cmd for the GUI.
// - Run runpod-client.cmd with arguments for CLI mode.
// Uses built-in Windows Script Host / HTA, WinHTTP, MSXML and ADODB.
//
// SECURITY:
// Put your real RunPod credentials below ONLY in your local copy.
// This repository is public, so never commit a real API key.

var RUNPOD_API_KEY = "PASTE_YOUR_RUNPOD_API_KEY_HERE";
var RUNPOD_ENDPOINT_ID = "PASTE_YOUR_RUNPOD_ENDPOINT_ID_HERE";

var RunPodClient = (function () {
    function getEnv(name) {
        try {
            var shell = new ActiveXObject("WScript.Shell");
            var env = shell.Environment("PROCESS");
            return String(env(name) || "");
        } catch (e) {
            return "";
        }
    }

    function usableConfiguredValue(value) {
        value = String(value || "").replace(/^\s+|\s+$/g, "");
        if (!value) return "";
        if (value.indexOf("PASTE_YOUR_") === 0) return "";
        return value;
    }

    function getApiKey() {
        return usableConfiguredValue(RUNPOD_API_KEY) || getEnv("RUNPOD_API_KEY");
    }

    function getEndpointId() {
        return usableConfiguredValue(RUNPOD_ENDPOINT_ID) || getEnv("RUNPOD_ENDPOINT_ID");
    }

    function getCredentialStatus() {
        var key = getApiKey();
        var endpoint = getEndpointId();
        return {
            apiKeyConfigured: !!key,
            endpointConfigured: !!endpoint,
            endpointId: endpoint,
            apiKeyPreview: key ? (key.length > 8 ? key.substring(0, 4) + "..." + key.substring(key.length - 4) : "configured") : ""
        };
    }

    function readBinary(path) {
        var stream = new ActiveXObject("ADODB.Stream");
        stream.Type = 1;
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
        stream.SaveToFile(path, 2);
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

    function parseJson(text) {
        if (typeof JSON !== "undefined" && JSON.parse) {
            return JSON.parse(text);
        }
        return eval("(" + text + ")");
    }

    function normalizeOptions(input) {
        input = input || {};
        return {
            prompt: String(input.prompt || ""),
            image: String(input.image || ""),
            strength: input.strength === undefined || input.strength === "" ? 0.70 : parseFloat(input.strength),
            steps: input.steps === undefined || input.steps === "" ? 35 : parseInt(input.steps, 10),
            guidance: input.guidance === undefined || input.guidance === "" ? 7.5 : parseFloat(input.guidance),
            seed: input.seed === undefined || input.seed === "" || input.seed === null ? null : parseInt(input.seed, 10),
            output: String(input.output || "skin.png"),
            format: String(input.format || "modern"),
            negative: String(input.negative || "")
        };
    }

    function validateOptions(opts) {
        if (!getEndpointId()) {
            throw new Error("RUNPOD_ENDPOINT_ID is missing. Edit the top of runpod-client.js and paste your endpoint ID.");
        }
        if (!getApiKey()) {
            throw new Error("RUNPOD_API_KEY is missing. Edit the top of runpod-client.js and paste your API key.");
        }
        if (!opts.prompt && !opts.image) {
            throw new Error("Type a prompt, choose a reference image, or use both.");
        }
        if (opts.format !== "modern" && opts.format !== "legacy") {
            throw new Error("Format must be modern or legacy.");
        }
        if (isNaN(opts.strength) || opts.strength < 0 || opts.strength > 1.25) {
            throw new Error("Reference strength must be between 0 and 1.25.");
        }
        if (isNaN(opts.steps) || opts.steps < 10 || opts.steps > 60) {
            throw new Error("Steps must be between 10 and 60.");
        }
        if (isNaN(opts.guidance) || opts.guidance < 1 || opts.guidance > 15) {
            throw new Error("Guidance must be between 1 and 15.");
        }
        if (opts.seed !== null && (isNaN(opts.seed) || opts.seed < 0 || opts.seed > 2147483647)) {
            throw new Error("Seed must be between 0 and 2147483647.");
        }
    }

    function buildJson(opts, imageBase64) {
        var parts = [];
        parts.push('"prompt":' + jsonString(opts.prompt));
        parts.push('"steps":' + opts.steps);
        parts.push('"guidance_scale":' + opts.guidance);
        parts.push('"format":' + jsonString(opts.format));

        if (opts.negative) {
            parts.push('"negative_prompt":' + jsonString(opts.negative));
        }
        if (imageBase64) {
            parts.push('"reference_image_base64":' + jsonString(imageBase64));
            parts.push('"reference_strength":' + opts.strength);
        }
        if (opts.seed !== null) {
            parts.push('"seed":' + opts.seed);
        }
        return '{"input":{' + parts.join(",") + '}}';
    }

    function generate(input, onStatus) {
        var opts = normalizeOptions(input);
        validateOptions(opts);
        var log = typeof onStatus === "function" ? onStatus : function () {};

        var fso = new ActiveXObject("Scripting.FileSystemObject");
        var imageBase64 = "";

        if (opts.image) {
            if (!fso.FileExists(opts.image)) {
                throw new Error("Image not found: " + opts.image);
            }
            var file = fso.GetFile(opts.image);
            if (file.Size > 6 * 1024 * 1024) {
                throw new Error("Reference image must be 6 MB or smaller.");
            }
            log("Encoding reference image...");
            imageBase64 = bytesToBase64(readBinary(file.Path));
        }

        var body = buildJson(opts, imageBase64);
        var endpointId = getEndpointId();
        var apiKey = getApiKey();
        var url = "https://api.runpod.ai/v2/" + endpointId + "/runsync?wait=300000";

        log("Sending request to RunPod...");
        var http = new ActiveXObject("WinHttp.WinHttpRequest.5.1");
        http.SetTimeouts(30000, 30000, 30000, 330000);
        http.Open("POST", url, false);
        http.SetRequestHeader("Authorization", "Bearer " + apiKey);
        http.SetRequestHeader("Content-Type", "application/json");
        http.Send(body);

        if (http.Status < 200 || http.Status >= 300) {
            throw new Error("RunPod HTTP " + http.Status + ": " + http.ResponseText);
        }

        var responseText = String(http.ResponseText);
        var result;
        try {
            result = parseJson(responseText);
        } catch (e) {
            throw new Error("Could not parse RunPod response: " + responseText);
        }

        if (String(result.status || "") !== "COMPLETED") {
            var detail = result.error ? String(result.error) : responseText;
            throw new Error("RunPod job failed. Status: " + String(result.status || "unknown") + "\n\n" + detail);
        }

        if (!result.output || !result.output.image_base64) {
            throw new Error("RunPod response does not contain output.image_base64.\n\n" + responseText);
        }

        var outputPath = fso.GetAbsolutePathName(opts.output);
        log("Saving skin...");
        saveBinary(outputPath, base64ToBytes(String(result.output.image_base64)));

        return {
            outputPath: outputPath,
            width: result.output.width || "",
            height: result.output.height || "",
            seed: result.output.seed,
            sourceMode: result.output.source_mode || "",
            raw: result
        };
    }

    return {
        generate: generate,
        getCredentialStatus: getCredentialStatus
    };
})();

(function runCommandLineModeIfNeeded() {
    if (typeof WScript === "undefined") {
        return;
    }

    function fail(message, code) {
        WScript.Echo("ERROR: " + message);
        WScript.Quit(code || 1);
    }

    function usage() {
        WScript.Echo("Minecraft Skin RunPod Client");
        WScript.Echo("");
        WScript.Echo("Double-click runpod-client.cmd to open the GUI.");
        WScript.Echo("");
        WScript.Echo("CLI examples:");
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
                case "--reference-strength": opts.strength = value; break;
                case "--steps": opts.steps = value; break;
                case "--guidance": opts.guidance = value; break;
                case "--seed": opts.seed = value; break;
                case "--output": opts.output = value; break;
                case "--format": opts.format = value; break;
                case "--negative": opts.negative = value; break;
                default: fail("Unknown option: " + key);
            }
        }
        return opts;
    }

    if (WScript.Arguments.length === 0) {
        usage();
        WScript.Quit(0);
    }

    try {
        var result = RunPodClient.generate(parseArgs(), function (message) {
            WScript.Echo(message);
        });

        WScript.Echo("Saved: " + result.outputPath);
        if (result.width && result.height) {
            WScript.Echo("Size: " + result.width + "x" + result.height);
        }
        if (result.seed !== undefined && result.seed !== null) {
            WScript.Echo("Seed: " + result.seed);
        }
        if (result.sourceMode) {
            WScript.Echo("Mode: " + result.sourceMode);
        }
    } catch (e) {
        fail(e.message || String(e));
    }
})();
