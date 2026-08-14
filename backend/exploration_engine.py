from typing import Dict, List, Any, Optional
import asyncio
import json
import random
import uuid
from datetime import datetime
from browser_automation import BrowserAutomation
from langchain_openai import ChatOpenAI
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ExplorationEngine:
    def __init__(self, session_id: str, config: Dict[str, Any]):
        self.session_id = session_id
        self.config = config
        self.browser = BrowserAutomation()
        # base_url lets this point at any OpenAI-compatible endpoint (GitHub
        # Models, Azure, a local proxy). Unset means api.openai.com.
        llm_kwargs = {
            'model': os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            'temperature': 0.7,
            'api_key': os.getenv("OPENAI_API_KEY"),
            # This runs once per exploration step. An unreachable endpoint (a
            # blocking proxy, for instance) stalls rather than refusing, so cap
            # the wait and don't let the client retry behind our back.
            'timeout': float(os.getenv("OPENAI_TIMEOUT", "20")),
            'max_retries': int(os.getenv("OPENAI_MAX_RETRIES", "0")),
        }
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            llm_kwargs['base_url'] = base_url

        # No key configured is a valid setup: exploration is a random walk and
        # doesn't need the LLM. Skip it outright instead of failing per step.
        self.llm = ChatOpenAI(**llm_kwargs) if llm_kwargs['api_key'] else None
        self.llm_failures = 0
        self.llm_enabled = self.llm is not None

        if self.llm is None:
            logger.info("No OPENAI_API_KEY set; exploring without LLM analysis.")

        # Stop calling the LLM after repeated failures so one bad key or a
        # rate-limited endpoint doesn't spam the log for an entire run.
        self.max_llm_failures = 3
        self.findings = []
        # get_page_state() returns a trailing window of an append-only log, so the
        # same console/network error resurfaces on every step. Track what we've
        # already reported to keep one issue from becoming dozens of findings.
        self.seen_finding_keys = set()
        self.visited_urls = set()
        self.exploration_paths = []
        self.current_step = 0
        
    async def explore(self, websocket_manager=None):
        """Main exploration loop"""
        try:
            # Initialize browser
            headless = self.config.get(
                'headless',
                os.getenv('HEADLESS', 'false').strip().lower() in ('1', 'true', 'yes')
            )
            await self.browser.initialize(
                browser_type=self.config.get('browser_type', 'chromium'),
                headless=headless
            )
            
            # Navigate to start URL
            start_url = self.config['start_url']
            await self.browser.navigate(start_url)
            self.visited_urls.add(start_url)
            
            # Send initial state
            if websocket_manager:
                await websocket_manager.send_message(self.session_id, {
                    'type': 'status',
                    'message': f'Started exploration at {start_url}',
                    'timestamp': datetime.now().isoformat()
                })
            
            # Exploration loop
            max_steps = self.config.get('depth', 5) * 10 # 10 actions per depth level

            # The UI collects max_time; honour it so a slow site can't run past
            # the budget the user set.
            max_time = float(self.config.get('max_time') or 0)
            deadline = (asyncio.get_running_loop().time() + max_time) if max_time > 0 else None
            stop_reason = 'step limit reached'

            while self.current_step < max_steps:
                if deadline is not None and asyncio.get_running_loop().time() >= deadline:
                    stop_reason = f'time budget of {int(max_time)}s reached'
                    logger.info("Stopping exploration: %s", stop_reason)
                    break

                self.current_step += 1
                
                # Get current page state
                page_state = await self.browser.get_page_state()
                
                # Analyze current state
                analysis = await self.analyze_state(page_state)
                
                # Record exploration path
                path_entry = {
                    'step': self.current_step,
                    'url': page_state.get('url', ''),
                    'title': page_state.get('title', ''),
                    'action': analysis.get('action', 'unknown'),
                    'timestamp': datetime.now().isoformat()
                }
                self.exploration_paths.append(path_entry)
                
                # Send update
                if websocket_manager:
                    await websocket_manager.send_message(self.session_id, {
                        'type': 'state_update',
                        'path': path_entry,
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Check for findings
                findings = await self.check_for_findings(page_state, analysis)
                
                if findings:
                    for finding in findings:
                        self.findings.append(finding)
                        
                        if websocket_manager:
                            await websocket_manager.send_message(self.session_id, {
                                'type': 'finding',
                                'finding': finding,
                                'timestamp': datetime.now().isoformat()
                            })
                
                # Decide next action
                next_action = await self.decide_next_action(page_state, analysis)
                
                # Execute action
                if next_action['type'] == 'click':
                    await self.browser.click_element(next_action.get('selector', 'button'))
                elif next_action['type'] == 'type':
                    await self.browser.type_text(
                        next_action.get('selector', 'input'),
                        next_action.get('value', 'test')
                    )
                elif next_action['type'] == 'scroll':
                    await self.browser.scroll_page(
                        direction=next_action.get('direction', 'down'),
                        amount=next_action.get('amount', 500)
                    )
                elif next_action['type'] == 'back':
                    await self.browser.go_back()
                elif next_action['type'] == 'navigate':
                    await self.browser.navigate(next_action.get('url', start_url))
                
                # Small delay to simulate human behavior
                await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Exploration complete
            if websocket_manager:
                await websocket_manager.send_message(self.session_id, {
                    'type': 'complete',
                    'message': f'Exploration completed ({stop_reason}). Explored {self.current_step} states, found {len(self.findings)} issues.',
                    'timestamp': datetime.now().isoformat()
                })
            
            return {
                'success': True,
                'steps_explored': self.current_step,
                'findings': self.findings,
                'paths': self.exploration_paths,
                'visited_urls': list(self.visited_urls)
            }
            
        except Exception as e:
            logger.error(f"Exploration failed: {e}")
            
            if websocket_manager:
                await websocket_manager.send_message(self.session_id, {
                    'type': 'error',
                    'message': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            
            return {
                'success': False,
                'error': str(e),
                'findings': self.findings,
                'paths': self.exploration_paths
            }
            
        finally:
            await self.browser.close()
    
    FALLBACK_ANALYSIS = {
        'action': 'explore',
        'target': 'random',
        'reasoning': 'fallback',
        'potential_issue': None
    }

    async def analyze_state(self, page_state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current page state using LLM"""
        if not self.llm_enabled:
            return dict(self.FALLBACK_ANALYSIS)

        try:
            prompt = f"""
            Analyze this web page state and suggest next exploration action:
            
            URL: {page_state.get('url', '')}
            Title: {page_state.get('title', '')}
            
            Available elements:
            {page_state.get('dom', {}).get('buttons', [])[:5]}
            
            Console errors: {page_state.get('console_messages', [])[:3]}
            Failed requests: {page_state.get('failed_requests', [])[:3]}
            
            Suggest:
            1. What element to interact with next
            2. What type of action to perform
            3. Any potential issues you notice
            
            Format: JSON with keys: action, target, reasoning, potential_issue
            """
            
            # ainvoke takes a plain prompt; agenerate expects List[List[BaseMessage]]
            # and raises "'str' object has no attribute 'content'" on raw strings.
            response = await self.llm.ainvoke(prompt)
            analysis = self._message_text(response)
            parsed = self._parse_analysis(analysis)
            self.llm_failures = 0

            return {
                'action': parsed.get('action') or 'explore',
                'target': parsed.get('target') or 'next element',
                'reasoning': parsed.get('reasoning') or analysis,
                'potential_issue': parsed.get('potential_issue')
            }

        except Exception as e:
            self.llm_failures += 1
            logger.error(f"State analysis failed: {e}")

            if self.llm_failures >= self.max_llm_failures:
                self.llm_enabled = False
                logger.warning(
                    "Disabling LLM analysis for this run after %d consecutive "
                    "failures; exploration continues without it.",
                    self.llm_failures
                )

            return dict(self.FALLBACK_ANALYSIS)

    @staticmethod
    def _message_text(response: Any) -> str:
        """Flatten an LLM response into plain text."""
        content = getattr(response, 'content', response)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Newer LangChain versions return a list of content blocks
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and 'text' in block:
                    parts.append(block['text'])
            return '\n'.join(parts)
        return str(content)

    @staticmethod
    def _parse_analysis(text: str) -> Dict[str, Any]:
        """Pull the JSON object out of an LLM reply, tolerating prose/code fences."""
        if not text:
            return {}
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end <= start:
            return {}
        try:
            parsed = json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}


    async def check_for_findings(self, page_state: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for potential issues and bugs"""
        findings = []
        
        # Check console errors
        if self.config.get('explore_console', True):
            console_messages = page_state.get('console_messages', [])
            for msg in console_messages:
                # 'pageerror' entries are uncaught exceptions and matter as much
                # as console.error() ones.
                if msg.get('type') not in ('error', 'pageerror'):
                    continue
                text = msg.get('text', '')
                if not self._is_new_finding(f"console:{text}"):
                    continue
                findings.append(self._build_finding(
                    finding_type='console',
                    severity='medium',
                    title=f"Console Error: {text[:100]}",
                    description=text,
                    url=page_state.get('url', '')
                ))

        # Check failed requests
        if self.config.get('explore_network', True):
            failed_requests = page_state.get('failed_requests', [])
            for req in failed_requests:
                url = req.get('url', '')
                failure = req.get('failure', '')
                if not self._is_new_finding(f"network:{url}:{failure}"):
                    continue
                findings.append(self._build_finding(
                    finding_type='network',
                    severity='high',
                    title=f"Failed Request: {url[:100]}",
                    description=f"Request failed: {failure} ({url})",
                    url=page_state.get('url', '')
                ))

        # Check for visual issues (simplified)
        if self.config.get('explore_visual', True):
            broken_images = []
            try:
                broken_images = await self.browser.page.evaluate("""
                    () => Array.from(document.images)
                        .filter(img => img.complete && img.naturalWidth === 0)
                        .map(img => img.src)
                """)
            except Exception as e:
                # A navigation mid-evaluate destroys the execution context; that
                # must not abort the whole exploration run.
                logger.warning(f"Broken-image check skipped: {e}")

            if broken_images:
                key = 'visual:broken_images:' + '|'.join(sorted(broken_images))
                if self._is_new_finding(key):
                    findings.append(self._build_finding(
                        finding_type='visual',
                        severity='medium',
                        title=f"Broken Images Found ({len(broken_images)})",
                        description=f"Broken images: {broken_images[:5]}",
                        url=page_state.get('url', '')
                    ))

        return findings

    def _is_new_finding(self, key: str) -> bool:
        """True the first time a given issue is seen, False on every repeat."""
        if key in self.seen_finding_keys:
            return False
        self.seen_finding_keys.add(key)
        return True

    def _build_finding(self, finding_type: str, severity: str, title: str,
                       description: str, url: str) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            'id': str(uuid.uuid4()),
            'type': finding_type,
            'severity': severity,
            'title': title,
            'description': description,
            'url': url,
            'reproduction_steps': self.get_reproduction_steps(),
            'created_at': now,
            # The UI reads `timestamp`; `created_at` matches the DB column.
            'timestamp': now
        }
    
    def get_reproduction_steps(self) -> List[str]:
        """Generate reproduction steps from exploration history"""
        steps = []
        for path in self.exploration_paths[-5:]: # Last 5 steps
            steps.append(f"Step {path['step']}: {path['action']} at {path['url']}")
        return steps
    
    async def decide_next_action(self, page_state: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Decide next action to take"""
        # Get all interactive elements
        elements = await self.browser.get_all_elements()
        visible_elements = [el for el in elements if el.get('visible', False)]
        
        # Decide action based on analysis and randomness
        if visible_elements and random.random() < 0.7:
            # Interact with a visible element
            element = random.choice(visible_elements)
            selector = self._selector_for(element)

            if selector is None:
                return {'type': 'scroll', 'direction': 'down', 'amount': 500}

            if element['type'] in ('button', 'link'):
                return {'type': 'click', 'selector': selector}
            elif element['type'] == 'input':
                return {
                    'type': 'type',
                    'selector': selector,
                    'value': self.generate_test_input(element)
                }
        else:
            # Perform navigation action
            actions = ['scroll', 'back', 'navigate']
            action = random.choice(actions)
            
            if action == 'scroll':
                return {
                    'type': 'scroll',
                    'direction': random.choice(['up', 'down', 'bottom', 'top']),
                    'amount': random.randint(100, 1000)
                }
            elif action == 'back':
                return {'type': 'back'}
            else:
                return {
                    'type': 'navigate',
                    'url': self.config['start_url']
                }
        
        # Fallback
        return {'type': 'scroll', 'direction': 'down', 'amount': 500}
    
    @staticmethod
    def _selector_for(element: Dict[str, Any]) -> Optional[str]:
        """Build a usable selector for an element, or None if it isn't addressable."""
        if element.get('selector'):
            return element['selector']

        if element.get('type') == 'input':
            name = (element.get('name') or '').strip()
            if name:
                return f'input[name="{name}"]'
            return None

        # innerText is frequently multi-line; a text= selector needs one line,
        # and an empty one would match every node on the page.
        text = ' '.join((element.get('text') or '').split())
        if not text:
            return None
        return f'text="{text[:80]}"'

    def generate_test_input(self, element: Dict[str, Any]) -> str:
        """Generate test input based on element type"""
        input_type = element.get('inputType', 'text')
        
        if input_type == 'email':
            return 'test@example.com'
        elif input_type == 'number':
            return str(random.randint(-1000, 1000))
        elif input_type == 'date':
            return '2024-01-01'
        elif input_type == 'checkbox':
            return 'true'
        elif input_type == 'password':
            return 'TestPassword123!'
        else:
            return f'Test input {random.randint(1, 100)}'