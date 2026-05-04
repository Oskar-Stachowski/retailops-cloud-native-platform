function formatRole(role) {
  return String(role || "unknown").replaceAll("_", " ");
}

function UserSwitcher({ users = [], currentUserId, onChange }) {
  return (
    <label className="user-switcher" aria-label="Select demo user">
      <span>Demo user</span>
      <select
        value={currentUserId || "platform-admin"}
        onChange={(event) => onChange(event.target.value)}
      >
        {users.map((user) => (
          <option key={user.id} value={user.id}>
            {user.display_name} · {formatRole(user.role)}
          </option>
        ))}
      </select>
    </label>
  );
}

export default UserSwitcher;
