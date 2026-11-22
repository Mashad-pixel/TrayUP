(function () {
 const content=document.querySelector(".admin-content");
 content.innerHTML=`<h1 class="admin-title">Refunds</h1><div class="card table-card" style="margin-top:22px"><table class="data-table"><thead><tr><th>Order</th><th>Payment ID</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead><tbody id="refund-body"></tbody></table></div><p style="margin-top:10px;color:var(--muted);font-size:12px">Demo refunds · no payment provider action is performed</p>`;
 const rows=[{id:"TUP-4792",payment:"pay_demo_482",amount:95,status:"Not requested"},{id:"TUP-4788",payment:"pay_demo_477",amount:220,status:"Refunded"}];
 function render(){document.getElementById("refund-body").innerHTML=rows.map((r,i)=>`<tr><td>${r.id}</td><td>${r.payment}</td><td>₹${r.amount}</td><td><span class="status ${r.status==="Refunded"?"":"warning"}">${r.status}</span></td><td>${r.status==="Not requested"?`<button class="btn btn-secondary" data-refund="${i}">Request refund</button>`:"—"}</td></tr>`).join("");}
 document.getElementById("refund-body").addEventListener("click",e=>{const b=e.target.closest("[data-refund]");if(b&&confirm("Submit this demo refund request?")){rows[Number(b.dataset.refund)].status="Refund requested";render();trayNotify("Demo refund request submitted");}});
 render();
})();
