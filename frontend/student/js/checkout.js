(function(){
document.getElementById("app-header").innerHTML=trayComponents.header();
const cart=trayStorage.get("trayup-cart",[]);
const total=cart.reduce((sum,item)=>sum+item.price*item.qty,0);
const escapeHtml=(value)=>String(value??"").replace(/[&<>"']/g,(character)=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[character]));
const paidStatuses=new Set(["paid","captured","completed","success"]);
function confirmationUrl(order){
const data=order?.data||{};
const paymentStatus=String(data.payment_status||"").toLowerCase();
return paidStatuses.has(paymentStatus)
 ? `./order-placed-animation.html?receipt=${encodeURIComponent(data.order_number||"Pending")}`
 : "./confirmation.html";
}
document.getElementById("checkout-total").textContent=`₹${total.toLocaleString("en-IN")}`;
document.getElementById("summary").innerHTML=cart.length?cart.map(i=>`<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee"><span>${i.qty} × ${escapeHtml(i.name)}</span><strong>₹${i.price*i.qty}</strong></div>`).join(""):`<p style="color:var(--muted)">Your cart is empty</p>`;
document.getElementById("summary-food-images").innerHTML=cart.map(item=>`
<figure class="checkout-food-image">
 <img src="${escapeHtml(item.image||"")}" alt="${escapeHtml(item.name)}" loading="eager" onerror="this.style.display='none'">
 <figcaption><strong>${escapeHtml(item.name)}</strong><span>Qty ${Number(item.qty)||1}</span></figcaption>
</figure>`).join("");
const nameInput=document.getElementById("name");
const phoneInput=document.getElementById("phone");
const phoneError=document.getElementById("phone-error");
let phoneValidationRequested=false;
function validatePhone(showError){
const valid=trayValidation.phone(phoneInput.value);
phoneError.hidden=valid||!showError;
phoneInput.setAttribute("aria-invalid",String(!valid&&showError));
return valid;
}
nameInput.addEventListener("input",()=>nameInput.removeAttribute("aria-invalid"));
phoneInput.addEventListener("blur",()=>validatePhone(true));
phoneInput.addEventListener("input",()=>{if(phoneValidationRequested||!phoneError.hidden)validatePhone(true);});
document.getElementById("checkout-form").addEventListener("submit",async(event)=>{
event.preventDefault();
const name=nameInput.value.trim();
const phone=phoneInput.value.trim();
const instructions=document.getElementById("instructions").value.trim();
const paymentMethod=document.querySelector('input[name="payment_method"]:checked').value;
const paymentLabels={googlepay:"Google Pay",phonepe:"PhonePe",razorpay:"Razorpay",cash:"Cash on pickup"};
const paymentProvider=paymentLabels[paymentMethod]||"Payment";
const demoMode=window.TRAYUP_CONFIG?.demoMode!==false;
const paymentStatus=paymentMethod==="cash"?"cash_due":demoMode?"paid":"pending";
phoneValidationRequested=true;
const validPhone=validatePhone(true);
if(!trayValidation.required(name)){nameInput.setAttribute("aria-invalid","true");nameInput.focus();trayNotify("Please enter your name");return;}
if(!validPhone){phoneInput.focus();return;}
if(!cart.length){trayNotify("Your cart is empty");return;}
const submitButton=document.querySelector('#checkout-form button[type="submit"]');
const originalButtonText=submitButton.textContent;
submitButton.disabled=true;
if(paymentMethod!=="cash"&&demoMode){
 submitButton.textContent="Confirming payment…";
 await new Promise(resolve=>setTimeout(resolve,900));
 trayNotify("Payment successful");
}
if(demoMode){
 const savedOrder=window.trayDemoData.recordOrder({
  items:cart.map(item=>({productId:item.id,quantity:item.qty})),
  total,
  status:"received",
  paymentStatus,
  studentName:name,
  phoneNumber:phone,
  paymentMethod,
  paymentProvider,
  instructions
 });
 const demoOrder={success:true,data:{order_number:savedOrder.id,status:"received",payment_status:savedOrder.paymentStatus,payment_method:paymentMethod,payment_provider:paymentProvider,total_amount:total,items:cart,instructions,student_name:name,phone_number:phone,created_at:savedOrder.createdAt}};
 trayStorage.remove("trayup-cart");
 trayStorage.set("trayup-last-order",demoOrder);
 window.location.href=confirmationUrl(demoOrder);
 return;
}
try{
const payload={items:cart.map(i=>({menu_item_id:i.id,quantity:i.qty}))};
try{
 const response=await trayApi.post("/orders",payload);
 window.trayDemoData.recordOrder({
  id:response?.data?.order_number,
  items:cart.map(item=>({productId:item.id,quantity:item.qty})),
  total:Number(response?.data?.total_amount||total),
  status:response?.data?.status||"received",
  paymentStatus:response?.data?.payment_status||paymentStatus,
  studentName:name,
  phoneNumber:phone,
  paymentMethod,
  paymentProvider,
  instructions
 });
 trayStorage.remove("trayup-cart");
 const savedResponse={...response,data:{...(response?.data||{}),items:cart,student_name:name,phone_number:phone,instructions,payment_method:paymentMethod,payment_provider:paymentProvider,payment_status:response?.data?.payment_status||paymentStatus}};
 trayStorage.set("trayup-last-order",savedResponse);
 window.location.href=confirmationUrl(savedResponse);
}catch(apiError){
 // Demo fallback keeps this frontend fully usable before menu/payment APIs are available.
 if(apiError.status===401||apiError.status===404||apiError.status===500){
  const savedOrder=window.trayDemoData.recordOrder({
   items:cart.map(item=>({productId:item.id,quantity:item.qty})),
   total,
   status:"received",
   paymentStatus,
   studentName:name,
   phoneNumber:phone,
   paymentMethod,
   paymentProvider,
   instructions
  });
  const demoOrder={success:true,data:{order_number:savedOrder.id,status:"received",payment_status:savedOrder.paymentStatus,payment_method:paymentMethod,payment_provider:paymentProvider,total_amount:total,items:cart,instructions,student_name:name,phone_number:phone,created_at:savedOrder.createdAt}};
  trayStorage.remove("trayup-cart");
  trayStorage.set("trayup-last-order",demoOrder);
  window.location.href=confirmationUrl(demoOrder);
 }else throw apiError;
}
}catch(error){
if(error.status===401){trayNotify("Please sign in with a student account before placing an order");}
else{trayNotify(error.message||"The order could not be placed");}
submitButton.disabled=false;
submitButton.textContent=originalButtonText;
}
});
})();
