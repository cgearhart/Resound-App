
var audio_context;
var mediaStream;

var CLIP_LENGTH = 8000;   // length of recorded audio clip (in ms)
var TIMEOUT     = 20000;  // POST response timeout (in ms)

function setupAudio() {
    showResult("Please allow microphone access - note that mobile browsers are not currently supported.", 8000);
    try {
        // webkit & mozilla shim
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        navigator.getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;
        window.URL = window.URL || window.webkitURL;

        audio_context = new AudioContext();
        console.log('Audio context set up.');
    } catch (e) {
        alert('No web audio support in this browser!');
        showResult("Sorry!<br>Your browser is not supported.");
    }
    
    navigator.getUserMedia({audio: true},
        function (stream) {
            mediaStream = audio_context.createMediaStreamSource(stream);
            console.log('Media stream created.');
            document.getElementById("button").classList.toggle('disabled');
            showResult("");
        },
        function(e) { console.log('No live audio input: ' + e);
        showResult("Sorry!<br>Your microphone is unavailable.");
    });
}

function recordAudioClip(buttonDiv) {

    if (!mediaStream) return;  // abort if the stream hasn't been established
    
    recorder = new Recorder(mediaStream,
        {'workerPath': 'js/Recorderjs/recorderWorker.js'});
    console.log('Recorder initialized - begin recording');
    
    recorder.record();
    buttonDiv.style.pointerEvents = 'none';
    buttonDiv.classList.toggle('disabled');
    
    // Enable message display & activate spinner animation
    showDialog("Recording");
    showResult("");
    
    setTimeout(function () {
        console.log("Stop recording.");
        recorder.stop();
        buttonDiv.style.pointerEvents = 'auto';
        buttonDiv.classList.toggle('disabled');
        console.log("Convert to WAV & upload.");
        recorder.exportWAV(sendAudio);
        recorder.clear();
    }, CLIP_LENGTH);
}

function sendAudio(blob) {
    
    var request = new XMLHttpRequest();
    var result_div = document.getElementById("result");

    showDialog("Processing");

    request.onload = function() {
        
        console.log("Request complete.");
        console.log(request.responseText);
        
        disableDialog();

        if (request.status != 200) {
            console.log("Bad response code: " + request.status);
            showResult("There was a problem!<br>Please try again.");
        } else {
            try {
                response = JSON.parse(request.responseText);
                var message = "Best Match:<hr>" +
                              response.artist + " - " + response.title + "<br>" +
                              "(" + response.year + ")";
                showResult(message);
            } catch (err) {
                // write an error to the result div then fade it away after 8s
                console.log("Error!\n" + err.message);
                showResult("Sorry!<br>No Match Found.", 8000);
            }
        }
        
    };
    request.open("POST", "/id", true);
    
    request.timeout = TIMEOUT;
    request.ontimeout = function () {
        console.log("Request timeout.");
        disableDialog();
        showResult("Request timed out.<br>Please try again.", 8000);
    };
    
    request.send(blob);
}

function disableDialog() {

    var dialog_div = document.getElementById("dialogBox");
    dialog_div.classList.remove("visible");
    dialog_div.classList.add("hidden");
    document.getElementById("message").innerHTML = "";
}

function showDialog(message) {
    
    var dialog_div = document.getElementById("dialogBox");
    dialog_div.classList.remove("hidden");
    dialog_div.classList.add("visible");
    document.getElementById("message").innerHTML = message;
}

function showResult(message, duration) {

    var result_div = document.getElementById("result");
    result_div.className = "fadein";
    result_div.innerHTML = message;
    if (arguments.length > 1) {
        setTimeout(function() {
            result_div.className = "fadeout";
        }, duration);
    }
}
