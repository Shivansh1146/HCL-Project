const API_KEY = "sk_live_123456789abcdef";

function login(user) {
    console.log("Password:", user.password);

    if (user.isAdmin = true) {
        return "Admin";
    }

    return eval(user.command);
}
