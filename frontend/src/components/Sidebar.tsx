import { ChatIcon, CloseIcon, Logo, LogoutIcon, MicIcon, PlusIcon, SettingsIcon, TrashIcon } from './Icons'
import type { Conversation, User, VoiceProfile } from '../types'

interface Props {
  user: User
  path: string
  open: boolean
  conversations: Conversation[] | null
  voice: VoiceProfile | null
  onClose: () => void
  onNewConversation: () => void
  onDeleteConversation: (id: string) => void
  onLogout: () => void
}

export function Sidebar({
  user,
  path,
  open,
  conversations,
  voice,
  onClose,
  onNewConversation,
  onDeleteConversation,
  onLogout,
}: Props) {
  return (
    <>
      <div className={`scrim${open ? ' is-open' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside className={`sidebar${open ? ' is-open' : ''}`} aria-label="Main navigation">
        <div className="sidebar-top">
          <a className="brand" href="#/">
            <Logo size={30} />
            <span>Personal Voice AI</span>
          </a>
          <button type="button" className="icon-button icon-button-ghost sidebar-close" aria-label="Close menu" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        <button type="button" className="button button-primary button-block" onClick={onNewConversation}>
          <PlusIcon size={16} />
          New conversation
        </button>

        <nav className="sidebar-section sidebar-conversations" aria-label="Conversations">
          <p className="sidebar-heading">Conversations</p>
          {conversations === null ? (
            <p className="sidebar-empty">Loading…</p>
          ) : conversations.length === 0 ? (
            <p className="sidebar-empty">No conversations yet.</p>
          ) : (
            <ul className="conversation-list">
              {conversations.map((conversation) => {
                const active = path === `/conversation/${conversation.id}`
                return (
                  <li key={conversation.id} className={`conversation-item${active ? ' is-active' : ''}`}>
                    <a href={`#/conversation/${conversation.id}`} aria-current={active ? 'page' : undefined}>
                      <ChatIcon size={15} />
                      <span>{conversation.title}</span>
                    </a>
                    <button
                      type="button"
                      className="icon-button icon-button-ghost conversation-delete"
                      aria-label={`Delete ${conversation.title}`}
                      title="Delete conversation"
                      onClick={() => onDeleteConversation(conversation.id)}
                    >
                      <TrashIcon size={15} />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </nav>

        <div className="sidebar-footer">
          {/* With a voice, this manages it in Settings; without one, it starts enrollment. */}
          <a
            className={`nav-link${path === '/enroll' && !voice ? ' is-active' : ''}`}
            href={voice ? '#/settings' : '#/enroll'}
          >
            <MicIcon size={17} />
            <span className="nav-link-text">
              {voice ? voice.name : 'Create your voice'}
              <span className="nav-link-sub">{voice ? 'Voice ready' : 'Replies are text only'}</span>
            </span>
            <span className={`status-dot${voice ? ' is-ready' : ''}`} aria-hidden="true" />
          </a>
          <a className={`nav-link${path === '/settings' ? ' is-active' : ''}`} href="#/settings">
            <SettingsIcon size={17} />
            <span className="nav-link-text">Settings</span>
          </a>
          <div className="account-row">
            <span className="avatar" aria-hidden="true">{user.email.slice(0, 1).toUpperCase()}</span>
            <span className="account-email" title={user.email}>{user.email}</span>
            <button type="button" className="icon-button icon-button-ghost" aria-label="Log out" title="Log out" onClick={onLogout}>
              <LogoutIcon size={17} />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
