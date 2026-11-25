(async function () {
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const body=document.getElementById("orders-body");
  let orders=[];
  function render(){
    const q=document.getElementById("order-search").value.toLowerCase();
    const payment=document.getElementById("payment-filter").value.toLowerCase();
    const status=document.getElementById("status-filter").value.toLowerCase();
    const rows=orders.filter(o=>(!q||(String(o.order_number||"")+" "+String(o.student_name||"")).toLowerCase().includes(q))&&
      (!payment||String(o.payment_status||"").toLowerCase()===payment)&&
      (!status||String(o.status||"").toLowerCase()===status));
    body.innerHTML=rows.length?rows.map(o=>"<tr><td><strong>"+esc(o.order_number||o.id)+"</strong></td><td>"+
      esc(o.student_name||"Guest")+"</td><td>₹"+Number(o.total_amount||o.amount||0).toLocaleString("en-IN")+
      '</td><td><span class="status">'+esc(o.status||"—")+"</span></td><td>"+esc(o.payment_status||"—")+"</td></tr>"
    ).join(""):'<tr><td colspan="5">No matching orders</td></tr>';
  }
  function renderDemo(){
    orders=[["TUP-4825","Aarav Shah",310,"Preparing","Captured"],["TUP-4821","Meera Iyer",225,"Ready","Captured"],
      ["TUP-4818","Kabir Singh",280,"Preparing","Captured"],["TUP-4809","Zoya Khan",190,"Collected","Captured"]]
      .map((r,i)=>({id:i+1,order_number:r[0],student_name:r[1],total_amount:r[2],status:r[3],payment_status:r[4]}));
    body.insertAdjacentHTML("beforebegin",'<p class="status warning">Read-only demo data</p>'); render();
  }
  try{
    if(new URLSearchParams(location.search).get("demo")==="1") renderDemo();
    else {const r=await trayApi.get("/admin/orders");orders=r?.data?.orders||[];render();}
  }catch(error){
    body.textContent=error.status===401?"Please sign in to view administrator orders.":
      error.status===403?"This account does not have administrator access.":"Unable to load orders. Please retry.";
  }
  ["order-search","payment-filter","status-filter"].forEach(id=>
    document.getElementById(id).addEventListener(id==="order-search"?"input":"change",render));
})();
