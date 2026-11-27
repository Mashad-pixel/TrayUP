(function(){
const nav=[["Overview","dashboard.html"],["Menu","menu.html"],["Categories","categories.html"],["Orders","orders.html"],["Staff","staff.html"],["Reports","reports.html"],["Refunds","refunds.html"],["Settings","settings.html"]];
const active=document.body.dataset.page;
document.getElementById("admin-nav").innerHTML=nav.map(([name,file])=>`<a class="${file===active?"active":""}" href="./${file}">${name}</a>`).join("");
if(active!=="dashboard.html"){document.getElementById("logout")?.addEventListener("click",async(event)=>{const button=event.currentTarget;button.disabled=true;if(window.trayMode?.isDemo?.()){window.trayMode.exitDemo();window.location.href="./login.html";return;}try{await trayAuth.logout();window.location.href="./login.html";}catch(_){button.disabled=false;window.trayNotify?.("Could not sign out. Check your connection and try again.");}});}
})();
