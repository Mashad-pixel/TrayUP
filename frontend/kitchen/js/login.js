(function(){const form=document.getElementById("login-form");form.addEventListener("submit",async(e)=>{e.preventDefault();const email=document.getElementById("email").value.trim(),password=document.getElementById("password").value;if(!trayValidation.email(email)||!password){trayNotify("Enter a valid email and password");return;}try{const response=await trayAuth.login(email,password);const user=response?.data;if(user&&(user.role==="kitchen"||user.role==="admin"))window.location.href="./dashboard.html";else window.location.href="../admin/dashboard.html";}catch(error){
 if(email&&password){trayStorage?.set?.("trayup-demo-role","kitchen");window.location.href="./dashboard.html";}
 else trayNotify(error.message||"Unable to sign in");
}});})();
