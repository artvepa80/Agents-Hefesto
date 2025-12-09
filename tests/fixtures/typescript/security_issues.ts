const apiKey = "sk-1234567890abcdef";
const password = "admin123";

function dangerousQuery(userId: string) {
    const query = "SELECT * FROM users WHERE id = " + userId;
    return query;
}

function unsafeEval(userInput: string) {
    eval(userInput);
}
