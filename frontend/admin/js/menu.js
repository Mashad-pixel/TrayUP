(function () {
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);

  let items=trayStorage.get("trayup-admin-menu",[
    {id:1,name:"Masala Dosa",category:"Breakfast",price:75,available:true},
    {id:2,name:"Paneer Butter Masala",category:"Lunch",price:140,available:true},
    {id:3,name:"Loaded Veg Pizza",category:"Snacks",price:160,available:true},
    {id:4,name:"Poha with Tea",category:"Breakfast",price:55,available:false}
  ]);
  const content=document.querySelector(".admin-content");
  content.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center"><h1 class="admin-title">Menu items</h1><button class="btn btn-primary" id="add-item" type="button">Add item</button></div><div class="card table-card" style="margin-top:22px"><table class="data-table"><thead><tr><th>Item</th><th>Category</th><th>Price</th><th>Availability</th><th>Actions</th></tr></thead><tbody id="menu-body"></tbody></table></div>`;
  function render(){trayStorage.set("trayup-admin-menu",items);document.getElementById("menu-body").innerHTML=items.map(i=>`<tr><td><strong>${esc(i.name)}</strong></td><td>${esc(i.category)}</td><td>₹${Number(i.price).toLocaleString("en-IN")}</td><td><span class="status ${i.available?"":"danger"}">${i.available?"Available":"Unavailable"}</span></td><td><button class="btn btn-secondary" data-edit="${esc(i.id)}" type="button">Edit</button> <button class="btn btn-secondary" data-toggle="${esc(i.id)}" type="button">${i.available?"Disable":"Enable"}</button> <button class="btn" data-delete="${esc(i.id)}" type="button" style="color:var(--danger)">Delete</button></td></tr>`).join("");}
  content.addEventListener("click",e=>{
    const add=e.target.closest("#add-item"),edit=e.target.closest("[data-edit]"),toggle=e.target.closest("[data-toggle]"),remove=e.target.closest("[data-delete]");
    if(add){const name=prompt("Item name");if(!name)return;const price=Number(prompt("Price in INR","100"));const category=prompt("Category","Snacks");if(!price||price<0)return;items.push({id:Date.now(),name,price,category:category||"Meals",available:true});render();trayNotify("Demo menu item added");}
    if(edit){const item=items.find(i=>i.id===Number(edit.dataset.edit));if(!item)return;const name=prompt("Item name",item.name);const price=Number(prompt("Price",item.price));if(name&&price>0){item.name=name;item.price=price;render();trayNotify("Demo item updated");}}
    if(toggle){const item=items.find(i=>i.id===Number(toggle.dataset.toggle));item.available=!item.available;render();trayNotify("Availability updated");}
    if(remove&&confirm("Delete this menu item?")){items=items.filter(i=>i.id!==Number(remove.dataset.delete));render();trayNotify("Demo item deleted");}
  });
  render();
})();
