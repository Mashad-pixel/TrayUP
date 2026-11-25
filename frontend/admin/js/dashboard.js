(function () {
  const nav = [["Overview","dashboard.html"],["Menu","menu.html"],["Categories","categories.html"],["Orders","orders.html"],["Staff","staff.html"],["Reports","reports.html"],["Refunds","refunds.html"],["Settings","settings.html"]];
  const esc = v => String(v ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  document.getElementById("admin-nav").innerHTML = nav.map(([name,file]) =>
    '<a class="' + (file==="dashboard.html"?"active":"") + '" href="./' + file + '">' + esc(name) + "</a>"
  ).join("");
  function renderOrders(orders) {
    const body=document.getElementById("admin-orders");
    body.innerHTML=orders.length?orders.slice(0,8).map(o =>
      "<tr><td>"+esc(o.order_number||o.id)+"</td><td>"+esc(o.student_name||"Guest")+
      "</td><td>₹"+Number(o.total_amount||o.amount||0).toLocaleString("en-IN")+
      '</td><td><span class="status">'+esc(o.status||"—")+"</span></td><td>"+esc(o.payment_status||"—")+"</td></tr>"
    ).join(""):'<tr><td colspan="5">No orders available</td></tr>';
  }
  function renderDemo() {
    const demo=[["Total orders","148"],["Today's orders","24"],["Today's revenue","₹18,450"],["Successful payments","23"]];
    document.getElementById("admin-stats").innerHTML=demo.map(([label,value])=>
      '<div class="admin-card"><span>'+label+'</span><div class="value">'+value+"</div></div>"
    ).join("")+'<div class="admin-card" style="grid-column:1/-1"><span class="status warning">Read-only demo data</span></div>';
    renderOrders([{order_number:"TUP-4825",student_name:"Aarav Shah",total_amount:310,status:"Preparing",payment_status:"Captured"},
      {order_number:"TUP-4821",student_name:"Meera Iyer",total_amount:225,status:"Ready",payment_status:"Captured"}]);
  }
  async function load() {
    if (new URLSearchParams(location.search).get("demo")==="1") return renderDemo();
    try {
      const response=await trayApi.get("/admin/orders");
      const orders=response?.data?.orders||[];
      const total=orders.reduce((sum,o)=>sum+Number(o.total_amount||o.amount||0),0);
      const stats=[["Orders",orders.length],["Total value","₹"+total.toLocaleString("en-IN")],
        ["Paid",orders.filter(o=>o.payment_status==="captured").length],
        ["Pending",orders.filter(o=>o.status==="received").length]];
      document.getElementById("admin-stats").innerHTML=stats.map(([label,value])=>
        '<div class="admin-card"><span>'+esc(label)+'</span><div class="value">'+esc(value)+"</div></div>"
      ).join("");
      renderOrders(orders);
    } catch(error) {
      const message=error.status===401?"Please sign in to view administrator data.":
        error.status===403?"This account does not have administrator access.":"Unable to load administrator data. Please retry.";
      document.getElementById("admin-stats").textContent=message;
      document.getElementById("admin-orders").textContent=message;
      if(error.status===401||error.status===403){
        document.getElementById("admin-stats").innerHTML='<div class="admin-card"><span>'+esc(message)+
          '</span><div class="value" style="font-size:18px"><a href="./login.html">Sign in</a></div></div>';
      }
    }
  }
  document.getElementById("logout").addEventListener("click",async()=>{
    try{await trayAuth.logout();}catch(_){} location.href="./login.html";
  });
  load();
})();
