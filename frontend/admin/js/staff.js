(function () {
 let staff=trayStorage.get("trayup-admin-staff",[
  {id:1,name:"Neha Kapoor",email:"neha@canteen.edu",role:"Kitchen",active:true},
  {id:2,name:"Rohan Das",email:"rohan@canteen.edu",role:"Kitchen",active:true},
  {id:3,name:"Priya Nair",email:"priya@canteen.edu",role:"Admin",active:false}
 ]);
 const content=document.querySelector(".admin-content");
 content.innerHTML=`<div style="display:flex;justify-content:space-between"><h1 class="admin-title">Staff accounts</h1><button class="btn btn-primary" id="add-staff">Add staff</button></div><div class="card table-card" style="margin-top:22px"><table class="data-table"><thead><tr><th>Name</th><th>Login identifier</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody id="staff-body"></tbody></table></div>`;
 function render(){trayStorage.set("trayup-admin-staff",staff);document.getElementById("staff-body").innerHTML=staff.map(s=>`<tr><td><strong>${s.name}</strong></td><td>${s.email}</td><td>${s.role}</td><td><span class="status ${s.active?"":"danger"}">${s.active?"Active":"Inactive"}</span></td><td><button class="btn btn-secondary" data-role="${s.id}">Edit role</button> <button class="btn btn-secondary" data-toggle="${s.id}">${s.active?"Deactivate":"Activate"}</button></td></tr>`).join("");}
 content.addEventListener("click",e=>{const add=e.target.closest("#add-staff"),role=e.target.closest("[data-role]"),toggle=e.target.closest("[data-toggle]");if(add){const name=prompt("Staff name");const email=prompt("Login identifier");if(name&&email){staff.push({id:Date.now(),name,email,role:"Kitchen",active:true});render();}}if(role){const s=staff.find(x=>x.id===Number(role.dataset.role));const next=prompt("Role (Admin or Kitchen)",s.role);if(next==="Admin"||next==="Kitchen"){s.role=next;render();}}if(toggle){const s=staff.find(x=>x.id===Number(toggle.dataset.toggle));s.active=!s.active;render();}});
 render();
})();
