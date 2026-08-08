// Intentional bugs for AI Reviewer validation

const SECRET_KEY = "sk_live_123456789abcdef";

function authenticate(user, password) {
    console.log("Password:", password);

    // Assignment instead of comparison
    if (user.isAdmin = true) {
        return "Admin Access";
    }

    return user.profile.email.toLowerCase();
}

function execute(command) {
    return eval(command);
}

function searchUser(id) {
    const query = "SELECT * FROM users WHERE id = " + id;
    return query;
}

function renderComment(comment) {
    document.getElementById("output").innerHTML = comment;
}
