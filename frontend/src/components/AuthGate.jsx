import { useEffect, useState } from "react";
import { fetchAutomationState, requestAuthCode, verifyAuthCode } from "../api/client.js";

export default function AuthGate({ children }) {
  const [status, setStatus] = useState("checking");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let alive = true;
    fetchAutomationState()
      .then(() => {
        if (alive) setStatus("ok");
      })
      .catch((error) => {
        if (!alive) return;
        setStatus(String(error.message || "").includes("ui_auth_required") ? "login" : "login");
      });
    return () => {
      alive = false;
    };
  }, []);

  async function handleSendCode() {
    setMessage("Отправляю код в Telegram...");
    await requestAuthCode();
    setMessage("Код отправлен в разрешенный Telegram чат. Он живет 5 минут.");
  }

  async function handleVerify(event) {
    event.preventDefault();
    setMessage("Проверяю код...");
    await verifyAuthCode(code);
    setStatus("ok");
  }

  if (status === "ok") return children;

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-eyebrow">fin.zs-app.ru</div>
        <h1>Вход в торговый cockpit</h1>
        <p>
          Доступ закрыт. Код приходит только в Telegram, который указан в env на сервере.
        </p>
        <button type="button" className="primary" onClick={handleSendCode}>
          Получить код в Telegram
        </button>
        <form onSubmit={handleVerify} className="auth-form">
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="6-значный код"
            inputMode="numeric"
            autoComplete="one-time-code"
          />
          <button type="submit" className="ghost">Войти</button>
        </form>
        {message ? <div className="auth-message">{message}</div> : null}
      </section>
    </main>
  );
}
