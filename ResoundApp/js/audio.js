
var audio_context;
var mediaStream;

var CLIP_LENGTH = 7000;  // length of recorded audio clip (in ms)
var TIMEOUT     = 20000;  // POST response timeout (in ms)

function setupAudio() {
    try {
        // webkit & mozilla shim
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        navigator.getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;
        window.URL = window.URL || window.webkitURL;

        audio_context = new AudioContext();
        console.log('Audio context set up.');
    } catch (e) {
        alert('No web audio support in this browser!');
    }
    
    navigator.getUserMedia({audio: true},
        function (stream) {
            mediaStream = audio_context.createMediaStreamSource(stream);
            console.log('Media stream created.');
        },
        function(e) { console.log('No live audio input: ' + e);
    });
}

function recordAudioClip(buttonDiv) {
    /*
    *  Record a 10 second audio clip from the microphone and send the contents
    *  as a file blob in a POST request to the webserver backend
    */

    if (!mediaStream) return;  // abort if the stream hasn't been established
    
    recorder = new Recorder(mediaStream,
        {'workerPath': 'js/Recorderjs/recorderWorker.js'});
    console.log('Recorder initialized - begin recording');
    
    recorder.record();
    buttonDiv.style.pointerEvents = 'none';
    buttonDiv.classList.toggle('disabled');
    
    // TODO: activate animations
    
    setTimeout(
        function () {
            console.log("Stop recording.");
            recorder.stop();
            buttonDiv.style.pointerEvents = 'auto';
            buttonDiv.classList.toggle('disabled');
            recorder.exportWAV(sendAudio);
            recorder.clear();
        },
        CLIP_LENGTH);
}

function sendAudio(blob) {
    /*
    *  Make an HTTP POST request including a file blob in a POST request to 
    *  the webserver backend for identification
    */
    console.log("Convert to WAV & upload.");
    var request = new XMLHttpRequest();
    request.onload = function() {
        console.log("Request finished.");
        console.log(request.responseText);
        if (request.status === 200) {
            window.location.href = window.location.origin + "/id/" + request.responseText;
        } else {
            console.log("Error!\n" + request.responseText);
        }
    };
    request.open("POST", "/id", true);
    request.timeout = TIMEOUT;
    request.ontimeout = function () {
        console.log("Request timeout.");
        // window.location.href = window.location.origin + "/id/";
    };
    request.send(blob);
}
