(function(){
document.getElementById("app-header").innerHTML=trayComponents.header("My Orders");
const target=document.getElementById("tracking");
async function load(){
try{
const response=await trayApi.get("/orders");
const orders=response?.data?.orders||[];
if(!orders.length){
 const demo=trayStorage.get("trayup-last-order",null)?.data;
 if(demo){orders.push(demo);}
}
if(!orders.length){target.innerHTML=`<div class="empty-state"><h3>No active orders</h3><p>When you place an order, its live status will appear here.</p></div>`;return;}
target.innerHTML=orders.map(order=>`
<div style="padding:10px 0;border-bottom:1px solid #eee">
<div style="display:flex;justify-content:space-between;align-items:center"><strong>${order.order_number||"Order"}</strong><span class="status">${order.status||"received"}</span></div>
<p style="color:var(--muted);margin-top:8px;font-size:13px">${order.created_at||""}</p>
</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:18px 0">
${["received","preparing","ready","collected"].map((status,i)=>{
const current=["received","preparing","ready","collected"].indexOf(order.status||"received");
return `<div style="text-align:center"><div style="height:8px;border-radius:999px;background:${i<=current?"var(--green)":"#dde1dc"}"></div><span style="font-size:11px">${status}</span></div>`;
}).join("")}
</div>
<div style="display:flex;justify-content:space-between;margin-top:14px"><strong>Payment</strong><span class="status">${order.payment_status||"pending"}</span></div>
${Array.isArray(order.items)?`<div style="margin-top:14px">${order.items.map(i=>`<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #eee"><span>${i.qty||i.quantity||1} × ${i.name}</span><strong>₹${(i.price||0)*(i.qty||i.quantity||1)}</strong></div>`).join("")}</div>`:""}
<button class="btn btn-secondary" type="button" id="print-receipt" style="margin-top:16px">Print receipt</button>`).join("");
document.getElementById("print-receipt")?.addEventListener("click",()=>window.print());
}catch(error){
 const demo=trayStorage.get("trayup-last-order",null)?.data;
 if(demo){target.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center"><strong>${demo.order_number}</strong><span class="status">${demo.status||"received"}</span></div><p style="margin:12px 0;color:var(--muted)">Demo order · backend connection unavailable</p><div style="display:flex;justify-content:space-between"><strong>Payment</strong><span class="status">${demo.payment_status||"pending"}</span></div><button class="btn btn-secondary" type="button" onclick="window.print()" style="margin-top:16px">Print receipt</button>`;}
 else if(error.status===401)target.innerHTML=`<div class="empty-state"><h3>Sign in required</h3><p>Log in to view and track your orders.</p></div>`;
 else target.innerHTML=`<div class="empty-state"><h3>Unable to load orders</h3><p>${error.message||"Please try again later."}</p></div>`;
}
}
load();
})();
