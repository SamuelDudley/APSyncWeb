var config = {};

document.getElementById("register_btn").onclick = submitConfig;

function submitConfig(){
	config = {};
	$("form#dfsync_register_form :input").each(function(){
		console.log(this.type, this.id, this.value );
		config[this.id] = this.value
	});
	console.log(JSON.stringify(config))
	send(JSON.stringify({"dfsync_register" : config}))
};


