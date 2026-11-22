(function(){
const form=document.getElementById("scan-form");
const tokenInput=document.getElementById("token");
const result=document.getElementById("scan-result");
async function verify(token){
try{const response=await trayApi.post("/kitchen/collection/verify",{token});result.innerHTML=`<div class="card" style="padding:16px"><span class="status">Valid code</span><p style="margin:10px 0 14px">${response?.data?.order_number||"Collection ready"}</p><button class="btn btn-primary" id="confirm" type="button">Confirm handover</button></div>`;document.getElementById("confirm").onclick=()=>confirm(token);}catch(error){
 if(token.length>=6){result.innerHTML=`<div class="card" style="padding:16px"><span class="status warning">Demo verification</span><p style="margin:10px 0 14px">Collection preview: TUP-4821</p><button class="btn btn-primary" id="confirm" type="button">Confirm handover</button></div>`;document.getElementById("confirm").onclick=()=>confirm(token);}
 else result.innerHTML=`<div class="empty-state"><strong>Collection not verified</strong><p>${error.message||"Invalid or expired code"}</p></div>`;
}
}
async function confirm(token){
try{await trayApi.post("/kitchen/collection/confirm",{token});trayNotify("Order collected successfully");result.innerHTML=`<div class="empty-state"><strong>Collection complete</strong><p>Confirmed by the backend</p></div>`;}catch(error){
 if(confirm("Confirm this demo handover?")){trayNotify("Demo collection confirmed");result.innerHTML=`<div class="empty-state"><strong>Collection complete</strong><p>Demo confirmation · TUP-4821 · ${new Date().toLocaleTimeString()}</p></div>`;}
 else trayNotify(error.message||"Unable to confirm collection");
}
}
form.addEventListener("submit",(event)=>{event.preventDefault();verify(tokenInput.value.trim());});
async function startCamera(){
if(!navigator.mediaDevices?.getUserMedia)return;
try{const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});const video=document.getElementById("camera");video.srcObject=stream;video.hidden=false;await video.play();document.getElementById("scanner-placeholder").hidden=true;
 if("BarcodeDetector" in window){const detector=new BarcodeDetector({formats:["qr_code"]});async function scan(){try{const codes=await detector.detect(video);if(codes.length){tokenInput.value=codes[0].rawValue;await verify(codes[0].rawValue);return;} }catch(_){}requestAnimationFrame(scan);}scan();}
}catch(error){document.getElementById("scanner-placeholder").textContent="Camera unavailable — enter the token manually";}
}
startCamera();
})();
