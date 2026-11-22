(async function(){
 let orders=[];
 try{const r=await trayApi.get("/admin/orders");orders=r?.data?.orders||[];}catch(e){
 if(e.status===401||e.status===403&&!trayStorage.get("trayup-demo-role","")){document.getElementById("orders-body").innerHTML=`<tr><td colspan="5">Administrator access required</td></tr>`;return;}
 orders=[["TUP-4825","Aarav Shah",310,"Preparing","Captured"],["TUP-4821","Meera Iyer",225,"Ready","Captured"],["TUP-4818","Kabir Singh",280,"Preparing","Captured"],["TUP-4809","Zoya Khan",190,"Collected","Captured"],["TUP-4802","Dev Patel",95,"Received","Pending"]].map((r,i)=>({id:i+1,order_number:r[0],student_name:r[1],total_amount:r[2],status:r[3],payment_status:r[4]}));
 }
 function render(){
 const query=document.getElementById("order-search").value.toLowerCase();
 const payment=document.getElementById("payment-filter").value.toLowerCase();
 const status=document.getElementById("status-filter").value.toLowerCase();
 const visible=orders.filter(o=>(!query||`${o.order_number} ${o.student_name||""}`.toLowerCase().includes(query))&&(!payment||String(o.payment_status||"").toLowerCase()===payment)&&(!status||String(o.status||"").toLowerCase()===status));
 document.getElementById("orders-body").innerHTML=visible.length?visible.map(o=>`<tr><td><strong>${o.order_number||o.id}</strong></td><td>${o.student_name||"Guest"}</td><td>₹${Number(o.total_amount||o.amount||0).toLocaleString("en-IN")}</td><td><span class="status">${o.status||"—"}</span></td><td>${o.payment_status||"—"}</td></tr>`).join(""):`<tr><td colspan="5">No matching orders</td></tr>`;
 }
 ["order-search","payment-filter","status-filter"].forEach(id=>document.getElementById(id).addEventListener(id==="order-search"?"input":"change",render));
 render();
})();
