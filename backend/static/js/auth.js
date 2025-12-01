const API_BASE = "http://127.0.0.1:5000"; 

function getSessionUser() {
    const userJson = localStorage.getItem("user");
    return userJson ? JSON.parse(userJson) : null;
}

function saveSession(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
}

function clearSession() {
    localStorage.removeItem("token"); 
    localStorage.removeItem("user");
}

async function request(path, method = "GET", body = null) {
    const token = localStorage.getItem("token");
   
    const fullPath = path.startsWith("http") ? path : `${API_BASE}${path}`; 
    
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;

    const opts = {
        method,
        headers,
        body: body ? JSON.stringify(body) : null
    };

    const res = await fetch(fullPath, opts);
    let json;
    try { json = await res.json(); } catch(e) { json = null; }

    if (res.status === 401) {
        console.error("Token expired or unauthorized. Logging out.");
        clearSession();
        window.location.href = "/login.html"; 
    }
    
    return { ok: res.ok, status: res.status, data: json };
}



document.addEventListener("DOMContentLoaded", () => {
    const sessionUser = getSessionUser();
    if (sessionUser && sessionUser.change_password === true) {
    if (!window.location.href.includes("change_password")) {
        window.location.href = "/static/change_password.html";
    }
}

    // --- LOGIN FORM SUBMISSION ---
    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            e.preventDefault();
            document.getElementById("error").innerText = "";
            const email = document.getElementById("email").value.trim();
            const password = document.getElementById("password").value;
            if (!email || !password) {
                document.getElementById("error").innerText = "Email and password are required";
                return;
            }

            const result = await request("/api/auth/login", "POST", { email, password });
            
            if (!result.ok) {
                const msg = result.data?.message || result.data?.msg || `Login failed (${result.status})`;
                document.getElementById("error").innerText = msg;
                return;
            }

            // success
            const token = result.data.access_token;
            const user = result.data.user;
            if (!token) {
                document.getElementById("error").innerText = "No token returned from server";
                console.error("No token", result);
                return;
            }

            saveSession(token, user);
            
            // Your original redirect logic
            const role = user?.role;
            if (role === "admin") window.location = "/static/admin.html";
            else if (role === "manager") window.location = "/static/manager.html";
            else window.location = "/static/employee.html";
        });
    }

    // --- LOGOUT BUTTON ---
    const logoutButton = document.getElementById("logoutButton");
    if (logoutButton) {
        logoutButton.addEventListener("click", () => {
            clearSession();
            window.location.href = "/login.html"; 
        });
    }

    // Admin create user form (unchanged)
    const createUserForm = document.getElementById("createUserForm");
    if (createUserForm) {
        createUserForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const body = {
                name: document.getElementById("name").value,
                email: document.getElementById("email").value,
                position: document.getElementById("position").value,
                role: document.getElementById("role").value,
                password: document.getElementById("password").value
            };
            const token = localStorage.getItem("token");
            const headers = { "Content-Type": "application/json" };
            if (token) headers["Authorization"] = "Bearer " + token;
            const res = await fetch("/api/users", { method:"POST", headers, body: JSON.stringify(body) });
            const j = await res.json();
            document.getElementById("result").innerText = res.ok ? "Created user id="+j.user.id : "Error: "+(j.msg||j.message||JSON.stringify(j));
        });
    }
});
