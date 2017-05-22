var data_stream = {};

function update_data_stream(mavlink_data){
	if (mavlink_data.mavpackettype){
		data_stream[mavlink_data.mavpackettype] = mavlink_data;
		if (mavlink_data.mavpackettype == 'HEARTBEAT') {
			handle_HEARTBEAT();
		}
	}
}

function handle_HEARTBEAT(){
	if (data_stream.HEARTBEAT){
		document.getElementById("heartbeat_text").innerHTML = JSON.stringify(data_stream.HEARTBEAT);
	}

}