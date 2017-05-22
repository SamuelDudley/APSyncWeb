  	var config = {};
  	
  	document.getElementById("submit_btn").onclick = submitConfig;
  	
  	function submitConfig(){
  		config = {};
  		$("form#configuration_form :input").each(function(){
  			console.log(this.type, this.id, this.value );
  			config[this.id] = this.value
  		});
  		console.log(JSON.stringify(config))
  		send(JSON.stringify({"config" : config}))
  	};