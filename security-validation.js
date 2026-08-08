// Final validation test for AI Code Reviewer

const API_KEY = "sk_live_123456789abcdef";

function authenticate(user, password) {
    console.log("Password:", password);

    // Assignment instead of comparison
    if (user.isAdmin = true) {
        return "Admin";
    }

    return eval(user.command);
}
