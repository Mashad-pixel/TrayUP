(function(){
const nav=[["Overview","dashboard.html"],["Menu","menu.html"],["Categories","categories.html"],["Orders","orders.html"],["Staff","staff.html"],["Reports","reports.html"],["Refunds","refunds.html"],["Settings","settings.html"]];
document.getElementById("admin-nav").innerHTML=nav.map(([name,file])=>`<a class="${file==="dashboard.html"?"active":""}" href="./${file}">${name}</a>`).join("");
async function load(){
try{
const response=await trayApi.get("/admin/orders");
const orders=response?.data?.orders||[];
const total=orders.reduce((sum,o)=>sum+Number(o.total_amount||o.amount||0),0);
document.getElementById("admin-stats").innerHTML=[
["Orders",orders.length],["Total value",`₹${total.toLocaleString("en-IN")}`],["Paid",orders.filter(o=>o.payment_status==="captured").length],["Pending",orders.filter(o=>o.status==="received").length]
].map(([label,value])=>`<div class="admin-card"><span>${label}</span><div class="value">${value}</div></div>`).join("");
document.getElementById("admin-orders").innerHTML=orders.length?orders.slice(0,8).map(o=>`<tr><td>${o.order_number||o.id}</td><td>${o.student_name||"Guest"}</td><td>₹${Number(o.total_amount||o.amount||0).toLocaleString("en-IN")}</td><td><span class="status">${o.status||"—"}</span></td><td>${o.payment_status||"—"}</td></tr>`).join(""):`<tr><td colspan="5">No orders available</td></tr>`;
}catch(error){
const unauthorized=error.status===401||error.status===403;
 if(unauthorized&&!trayStorage?.get("trayup-demo-role","")){
  document.getElementById("admin-stats").innerHTML=`<div class="admin-card" style="grid-column:1/-1"><span>Administrator access required</span><div class="value" style="font-size:18px"><a href="./login.html" style="text-decoration:underline">Sign in</a></div></div>`;
  document.getElementById("admin-orders").innerHTML=`<tr><td colspan="5">Sign in to view orders</td></tr>`;
  return;
 }
 const demo=[["Total orders","148"],["Today's orders","24"],["Today's revenue","₹18,450"],["Successful payments","23"]];
 document.getElementById("admin-stats").innerHTML=demo.map(([label,value])=>`<div class="admin-card"><span>${label}</span><div class="value">${value}</div></div>`).join("")+`<div class="admin-card" style="grid-column:1/-1"><span class="status warning">Demo data · backend unavailable</span></div>`;
 document.getElementById("admin-orders").innerHTML=[["TUP-4825","Aarav Shah","₹310","Preparing","Captured"],["TUP-4821","Meera Iyer","₹225","Ready","Captured"],["TUP-4818","Kabir Singh","₹280","Preparing","Captured"]].map(row=>`<tr>${row.map((v,i)=>`<td>${i===3?`<span class="status">${v}</span>`:v}</td>`).join("")}</tr>`).join("");
}}
document.getElementById("logout").addEventListener("click",async()=>{try{await trayAuth.logout()}catch(_){}window.location.href="./login.html";});
load();
})();
