var url = "wss://" + location.host + "/websocket/";

var socket = null;
var isopen = false;
if ("WebSocket" in window) {
	// If WebSockets are supported by the users browser...
	window.setInterval(function(){
		check_websocket()
		}, 1000);
	// Attempt a connect / reconnect every second
} else {
	alert("WebSocket is required but is NOT supported by your Browser!");
}

function check_websocket(){
	if (isopen == false && socket == null) {
		open_websocket()
	}
};

function open_websocket() {
	socket = new WebSocket(url);
	socket.binaryType = "arraybuffer";
	socket.onopen = function() {
		console.log("WebSocket connected!");
		isopen = true;
	}
	socket.onerror = function(e) {
		console.log("WebSocket connection error:", e);
		socket = null;
        isopen = false;
	}
	socket.onmessage = function(e) {
		if (typeof e.data == "string") {
			console.log(e.data);
			//response = JSON.parse(e.data);
		}
	}
	socket.onclose = function(e) {
        console.log("WebSocket connection closed.");
        socket = null;
        isopen = false;
     }
};

function send(payload) {
	if (isopen && socket.readyState == 1) {
		socket.send(payload);
		console.log("WebSocket sent data.");               
	} else {
		console.log("WebSocket connection not avalable for send.")
    }
};