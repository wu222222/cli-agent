import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '../components/MessageBubble.vue'
import type { Message } from '@/types'

describe('MessageBubble', () => {
  const createMessage = (overrides: Partial<Message> = {}): Message => ({
    role: 'system',
    content: 'Test message',
    timestamp: '12:00:00',
    thought: '',
    type: 'text',
    ...overrides,
  })

  it('renders message content', () => {
    const message = createMessage({ content: 'Hello World' })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.text()).toContain('Hello World')
  })

  it('renders user role correctly', () => {
    const message = createMessage({ role: 'user' })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.find('.message').classes()).toContain('user')
  })

  it('renders system role correctly', () => {
    const message = createMessage({ role: 'system' })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.find('.message').classes()).toContain('system')
  })

  it('displays thought process when present', () => {
    const message = createMessage({ thought: 'Thinking about this...' })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.text()).toContain('Thinking about this...')
    expect(wrapper.find('.thought-process').exists()).toBe(true)
  })

  it('does not display thought section when empty', () => {
    const message = createMessage({ thought: '' })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.find('.thought-process').exists()).toBe(false)
  })

  it('renders timestamp', () => {
    const message = createMessage({ timestamp: '14:30:00' })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.text()).toContain('14:30:00')
  })

  it('renders agent name when provided', () => {
    const message = createMessage({ agent: 'WorkerAgent' })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.text()).toContain('WorkerAgent')
  })

  it('shows default role name when agent not provided', () => {
    const message = createMessage({ agent: undefined })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.text()).toContain('系统')
  })

  it('renders tool result type correctly', () => {
    const message = createMessage({
      type: 'tool_result',
      toolName: 'alpine_shell',
      command: 'ls -la',
    })
    const wrapper = mount(MessageBubble, { props: { message } })
    expect(wrapper.find('.tool-result-block').exists()).toBe(true)
    expect(wrapper.text()).toContain('alpine_shell')
  })

  it('truncates long commands', () => {
    const longCommand = 'a'.repeat(200)
    const message = createMessage({
      type: 'tool_result',
      toolName: 'test',
      command: longCommand,
    })
    const wrapper = mount(MessageBubble, { props: { message } })
    // Should be truncated to 120 chars + '...'
    expect(wrapper.text()).toContain('...')
  })
})
