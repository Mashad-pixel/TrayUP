(function(){
function updateTime(){document.getElementById("live-time").textContent=new Date().toLocaleString("en-IN",{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"});}
updateTime();setInterval(updateTime,30000);
async function load(){
try{
const response=await trayApi.get("/kitchen/orders");
const queue=response?.data?.queue||{};
render(queue);
}catch(error){
 if(error.status===401||error.status===403){
  document.getElementById("summary").innerHTML=`<div class="empty-state" style="grid-column:1/-1">Demo view is available. <button class="btn btn-primary" onclick="location.href='./login.html'" style="margin-left:8px">Sign in</button></div>`;
 } else {
  const demoQueue={received:[
   {id:101,order_number:"TUP-4821",created_at:"10:24 AM",payment_status:"captured",instructions:"Less spicy",items:[{name:"Masala Dosa",quantity:2},{name:"Cold Coffee",quantity:1}]},
   {id:102,order_number:"TUP-4825",created_at:"10:31 AM",payment_status:"captured",instructions:"Pack cutlery separately",items:[{name:"Grilled Chicken Bowl",quantity:1}]}
  ],preparing:[{id:103,order_number:"TUP-4818",created_at:"10:11 AM",payment_status:"captured",instructions:"",items:[{name:"Paneer Butter Masala",quantity:2}] }],ready:[{id:104,order_number:"TUP-4809",created_at:"9:58 AM",payment_status:"captured",instructions:"",items:[{name:"Cheese Chilli Sandwich",quantity:2},{name:"Mango Shake",quantity:2}] }],collected:[{id:105,order_number:"TUP-4802",created_at:"9:40 AM",payment_status:"captured",instructions:"",items:[{name:"Masala Dosa",quantity:1}] }]};
  render(demoQueue);
 }
}
}
function render(queue){
const statuses=["received","preparing","ready","collected"];
const counts=statuses.map(s=>Array.isArray(queue[s])?queue[s].length:0);
document.getElementById("summary").innerHTML=[["New",counts[0]],["Preparing",counts[1]],["Ready",counts[2]],["Collected",counts[3]]].map(([label,value])=>`<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join("");
statuses.forEach(status=>{
const column=document.querySelector(`[data-status="${status}"]`);
const title=column.querySelector("h2").outerHTML;
const orders=queue[status]||[];
column.innerHTML=title+(orders.length?orders.map(order=>`
<article class="order-ticket" data-order="${order.id}">
<header><span>${order.order_number||"Order"}</span><span>${order.created_at||""}</span></header>
<ul>${(order.items||[]).map(i=>`<li><span>${i.quantity||1} × ${i.name||i.menu_item_name||"Item"}</span></li>`).join("")}</ul>
${status==="received"?`<button class="btn btn-primary" data-next="preparing">Start preparing</button>`:""}
${status==="preparing"?`<button class="btn btn-primary" data-next="ready">Mark ready</button>`:""}
${status==="ready"?`<button class="btn btn-secondary" data-next="collected">Confirm collection</button>`:""}
</article>`).join(""):`<div class="empty-state" style="background:transparent">No orders</div>`);
});
}
document.getElementById("kitchen-board").addEventListener("click",async(e)=>{
const button=e.target.closest("[data-next]");
if(!button)return;
const ticket=button.closest("[data-order]");
const next=button.dataset.next==="collected"?"collected":button.dataset.next;
try{await trayApi.patch(`/kitchen/orders/${ticket.dataset.order}/status`,{status:next});trayNotify("Order status updated");load();}catch(error){
 if(confirm("Confirm this kitchen status update?")){
  document.querySelector(`[data-status="${next}"]`).appendChild(ticket);
  button.remove();
  trayNotify("Demo status updated");
 }
}
});
document.getElementById("logout").addEventListener("click",async()=>{try{await trayAuth.logout()}catch(_){}window.location.href="./login.html";});
load();
setInterval(load,15000);
})();
