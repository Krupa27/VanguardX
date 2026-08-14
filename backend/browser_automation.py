from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Dict, List, Any, Optional
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class BrowserAutomation:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.console_messages = []
        self.network_requests = []
        self.failed_requests = []
        
    async def initialize(self, browser_type: str = 'chromium', headless: bool = False):
        """Initialize browser instance"""
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser based on type
            if browser_type == 'chromium':
                self.browser = await self.playwright.chromium.launch(
                    headless=headless,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
            elif browser_type == 'firefox':
                self.browser = await self.playwright.firefox.launch(
                    headless=headless
                )
            elif browser_type == 'webkit':
                self.browser = await self.playwright.webkit.launch(
                    headless=headless
                )
            else:
                raise ValueError(f"Unsupported browser type: {browser_type}")
            
            # Create context with specific settings
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                ignore_https_errors=True,
                record_video_dir=None
            )
            
            # Create page
            self.page = await self.context.new_page()
            
            # Set up event listeners
            await self.setup_event_listeners()
            
            logger.info(f"Browser initialized: {browser_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def setup_event_listeners(self):
        """Set up event listeners for monitoring"""
        
        # Console messages
        self.page.on('console', lambda msg: self.console_messages.append({
            'type': msg.type,
            'text': msg.text,
            'location': msg.location,
            'timestamp': datetime.now().isoformat()
        }))
        
        # Page errors
        self.page.on('pageerror', lambda error: self.console_messages.append({
            'type': 'pageerror',
            'text': str(error),
            'timestamp': datetime.now().isoformat()
        }))
        
        # Network requests
        self.page.on('request', lambda request: self.network_requests.append({
            'url': request.url,
            'method': request.method,
            'resource_type': request.resource_type,
            'timestamp': datetime.now().isoformat()
        }))
        
        # Failed requests
        self.page.on('requestfailed', lambda request: self.failed_requests.append({
            'url': request.url,
            'method': request.method,
            'failure': request.failure,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to URL and capture state"""
        try:
            start_time = datetime.now()
            
            response = await self.page.goto(url, wait_until='networkidle', timeout=30000)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000
            
            return {
                'success': response.status if response else None,
                'url': self.page.url,
                'title': await self.page.title(),
                'duration_ms': duration,
                'status_code': response.status if response else None,
                'headers': response.headers if response else {}
            }
            
        except Exception as e:
            logger.error(f"Navigation failed to {url}: {e}")
            return {
                'success': False,
                'url': url,
                'error': str(e)
            }
    
    async def get_page_state(self) -> Dict[str, Any]:
        """Get current page state"""
        try:
            # Get DOM snapshot
            dom_snapshot = await self.page.evaluate("""
                () => {
                    return {
                        title: document.title,
                        url: window.location.href,
                        readyState: document.readyState,
                        bodyText: document.body ? document.body.innerText.substring(0, 5000) : '',
                        forms: Array.from(document.forms).map(form => ({
                            id: form.id,
                            action: form.action,
                            method: form.method,
                            fields: Array.from(form.elements).map(el => ({
                                type: el.type,
                                name: el.name,
                                id: el.id,
                                value: el.value
                            }))
                        })),
                        buttons: Array.from(document.querySelectorAll('button')).map(btn => ({
                            text: btn.innerText,
                            id: btn.id,
                            class: btn.className
                        })),
                        links: Array.from(document.querySelectorAll('a')).slice(0, 50).map(link => ({
                            href: link.href,
                            text: link.innerText
                        }))
                    };
                }
            """)
            
            # Take screenshot
            screenshot = await self.page.screenshot(full_page=False)
            
            return {
                'dom': dom_snapshot,
                'screenshot': screenshot,
                'url': self.page.url,
                'title': await self.page.title(),
                'console_messages': self.console_messages[-10:], # Last 10 messages
                'failed_requests': self.failed_requests[-10:]
            }
            
        except Exception as e:
            logger.error(f"Failed to get page state: {e}")
            return {}
    
    async def click_element(self, selector: str) -> Dict[str, Any]:
        """Click an element, preferring the first visible match."""
        try:
            target = await self.resolve_visible(selector)

            if target is None:
                return {'success': False, 'error': 'Element not found'}

            await target.click(timeout=5000)

            try:
                await self.page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                # Ad/telemetry-heavy pages may never reach networkidle. The click
                # already landed, so this is not a failure.
                logger.debug(f"networkidle not reached after clicking {selector}")

            return {
                'success': True,
                'selector': selector,
                'url': self.page.url
            }

        except Exception as e:
            logger.error(f"Failed to click element {selector}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def resolve_visible(self, selector: str, timeout: int = 5000):
        """Return the first visible match for a selector, or None.

        A text= selector routinely matches several nodes where the first is
        hidden (nav duplicates, mobile/desktop variants). Waiting on the first
        match alone just times out, so scan the matches for a visible one.
        """
        locator = self.page.locator(selector)

        try:
            count = await locator.count()
        except Exception as e:
            logger.debug(f"Could not count matches for {selector}: {e}")
            count = 0

        for i in range(min(count, 10)):
            candidate = locator.nth(i)
            try:
                if await candidate.is_visible():
                    return candidate
            except Exception:
                continue

        if count == 0:
            # Nothing in the DOM yet; give it a chance to render.
            try:
                await locator.first.wait_for(state='visible', timeout=timeout)
                return locator.first
            except Exception:
                return None

        return None

    async def type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """Type text into an input field"""
        try:
            element = await self.resolve_visible(selector)

            if element is None:
                return {'success': False, 'error': 'Element not found'}

            await element.fill(text, timeout=5000)

            return {
                'success': True,
                'selector': selector,
                'text': text,
                'url': self.page.url
            }
            
        except Exception as e:
            logger.error(f"Failed to type text into {selector}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def hover_element(self, selector: str) -> Dict[str, Any]:
        """Hover over an element"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=5000)
            
            if not element:
                return {'success': False, 'error': 'Element not found'}
            
            await element.hover()
            
            return {
                'success': True,
                'selector': selector
            }
            
        except Exception as e:
            logger.error(f"Failed to hover over element {selector}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def scroll_page(self, direction: str = 'down', amount: int = 500) -> Dict[str, Any]:
        """Scroll the page"""
        try:
            if direction == 'down':
                await self.page.evaluate(f'window.scrollBy(0, {amount})')
            elif direction == 'up':
                await self.page.evaluate(f'window.scrollBy(0, -{amount})')
            elif direction == 'bottom':
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            elif direction == 'top':
                await self.page.evaluate('window.scrollTo(0, 0)')
            
            await asyncio.sleep(0.5)
            
            return {
                'success': True,
                'direction': direction,
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"Failed to scroll page: {e}")
            return {'success': False, 'error': str(e)}
    
    async def go_back(self) -> Dict[str, Any]:
        """Navigate back"""
        try:
            await self.page.go_back(wait_until='networkidle')
            
            return {
                'success': True,
                'url': self.page.url
            }
            
        except Exception as e:
            logger.error(f"Failed to go back: {e}")
            return {'success': False, 'error': str(e)}
    
    async def go_forward(self) -> Dict[str, Any]:
        """Navigate forward"""
        try:
            await self.page.go_forward(wait_until='networkidle')
            
            return {
                'success': True,
                'url': self.page.url
            }
            
        except Exception as e:
            logger.error(f"Failed to go forward: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_all_elements(self) -> List[Dict[str, Any]]:
        """Get all interactive elements on the page"""
        try:
            elements = await self.page.evaluate("""
                () => {
                    const interactiveElements = [];
                    
                    // Get all buttons
                    document.querySelectorAll('button, [role="button"]').forEach(el => {
                        interactiveElements.push({
                            type: 'button',
                            text: el.innerText || el.textContent,
                            selector: el.id ? `#${el.id}` : null,
                            visible: el.offsetParent !== null
                        });
                    });
                    
                    // Get all links
                    document.querySelectorAll('a').forEach(el => {
                        interactiveElements.push({
                            type: 'link',
                            text: el.innerText || el.textContent,
                            href: el.href,
                            selector: el.id ? `#${el.id}` : null,
                            visible: el.offsetParent !== null
                        });
                    });
                    
                    // Get all inputs
                    document.querySelectorAll('input, textarea, select').forEach(el => {
                        interactiveElements.push({
                            type: 'input',
                            inputType: el.type,
                            name: el.name,
                            placeholder: el.placeholder,
                            selector: el.id ? `#${el.id}` : null,
                            visible: el.offsetParent !== null
                        });
                    });
                    
                    return interactiveElements;
                }
            """)
            
            return elements
            
        except Exception as e:
            logger.error(f"Failed to get elements: {e}")
            return []
    
    async def close(self):
        """Close browser and cleanup"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("Browser closed successfully")
            
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")