"""
Command-line interface for Agentic OS.

Provides user-facing commands:
- agentic-os status: Check system status
- agentic-os submit: Submit a task/intent
- agentic-os config: View/edit configuration
- agentic-os logs: View logs
"""

import argparse
import asyncio
import json
import sys
import logging, sys
from pathlib import Path
from typing import Optional

from .config import get_config, get_config_loader
from .logging_setup import setup_logging, get_logger
from .intent_bus import get_intent_bus, IntentType, Priority, reset_intent_bus


class CLI:
    """
    Command-line interface for Agentic OS.
    
    Handles command parsing, validation, and execution.
    """
    
    def __init__(self):
        """Initialize CLI."""
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create the argument parser.
        
        Returns:
            Configured ArgumentParser
        """
        parser = argparse.ArgumentParser(
            prog="agentic-os",
            description="Agentic OS - Userspace Sandwich Layer",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  agentic-os status              Show system status
  agentic-os submit "Summarize PDF"  Submit a task
  agentic-os config              Show current configuration
  agentic-os logs --tail 50      Show last 50 log lines
            """
        )
        
        subparsers = parser.add_subparsers(
            dest="command",
            help="Available commands"
        )
        
        # Status command
        status_parser = subparsers.add_parser(
            "status",
            help="Show system status"
        )
        status_parser.add_argument(
            "--json",
            action="store_true",
            help="Output in JSON format"
        )
        
        # Submit command
        submit_parser = subparsers.add_parser(
            "submit",
            help="Submit a task or intent"
        )
        submit_parser.add_argument(
            "intent",
            help="Task description or intent"
        )
        submit_parser.add_argument(
            "--priority",
            choices=["critical", "high", "normal", "low", "background"],
            default="normal",
            help="Task priority (default: normal)"
        )
        submit_parser.add_argument(
            "--source",
            default="cli",
            help="Source identifier (default: cli)"
        )
        submit_parser.add_argument(
            "--async",
            action="store_true",
            dest="async_mode",
            help="Submit without waiting for result"
        )
        
        # Config command
        config_parser = subparsers.add_parser(
            "config",
            help="View or edit configuration"
        )
        config_parser.add_argument(
            "--show",
            action="store_true",
            help="Show current configuration"
        )
        config_parser.add_argument(
            "--validate",
            action="store_true",
            help="Validate configuration file"
        )
        config_parser.add_argument(
            "--path",
            help="Path to custom config file"
        )
        
        # Logs command
        logs_parser = subparsers.add_parser(
            "logs",
            help="View system logs"
        )
        logs_parser.add_argument(
            "--tail",
            type=int,
            default=20,
            help="Number of lines to show (default: 20)"
        )
        logs_parser.add_argument(
            "--follow",
            action="store_true",
            help="Follow log output"
        )
        logs_parser.add_argument(
            "--component",
            help="Filter by component name"
        )
        
        # Version command
        subparsers.add_parser(
            "version",
            help="Show version information"
        )
        
        return parser
    
    async def cmd_status(self, args) -> int:
        """
        Show system status.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code
        """
        # In JSON mode, suppress ALL logging so stdout is pure JSON
        if args.json:
            logging.disable(logging.CRITICAL)
        
        try:
            config = get_config()
            bus = get_intent_bus()
            await bus.start()
            
            status = {
                "version": "0.1.0-phase1",
                "state": "running",
                "config": {
                    "base_dir": config.base_dir,
                    "planner_model": config.planner.model_name,
                    "scheduler_workers": config.scheduler.worker_count
                },
                "intent_bus": bus.get_stats(),
                "components": {
                    "planner": "not_implemented",
                    "memory": "not_implemented",
                    "scheduler": "not_implemented",
                    "tool_router": "not_implemented"
                }
            }
            
            await bus.stop()
            
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print("=== Agentic OS Status ===")
                print(f"Version: {status['version']}")
                print(f"State: {status['state']}")
                print(f"\nConfig:")
                print(f"  Base dir: {status['config']['base_dir']}")
                print(f"  Planner model: {status['config']['planner_model']}")
                print(f"  Scheduler workers: {status['config']['scheduler_workers']}")
                print(f"\nIntent Bus:")
                print(f"  Messages: {status['intent_bus']['message_count']}")
                print(f"  Dropped: {status['intent_bus']['dropped_count']}")
                print(f"  Subscribers: {status['intent_bus']['subscriber_counts']}")
                print(f"\nComponents:")
                for comp, state in status['components'].items():
                    print(f"  {comp}: {state}")
            
            return 0
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if args.json:
                logging.disable(logging.NOTSET)
    async def cmd_submit(self, args) -> int:
        """
        Submit a task or intent.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code
        """
        setup_logging()
        logger = get_logger("cli")
        
        try:
            config = get_config()
            bus = get_intent_bus()
            await bus.start()
            
            # Map priority string to enum
            priority_map = {
                "critical": Priority.CRITICAL,
                "high": Priority.HIGH,
                "normal": Priority.NORMAL,
                "low": Priority.LOW,
                "background": Priority.BACKGROUND
            }
            priority = priority_map[args.priority]
            
            # Publish intent
            message = await bus.publish_immediate(
                source=args.source,
                intent_type=IntentType.TASK_REQUEST,
                payload={
                    "intent": args.intent,
                    "submitted_at": asyncio.get_event_loop().time()
                },
                priority=priority
            )
            
            print(f"Task submitted successfully")
            print(f"Intent ID: {message.intent_id}")
            
            if not args.async_mode:
                # TODO: Wait for result in future phases
                print("Note: Result waiting not implemented in Phase 1")
            
            await bus.stop()
            return 0
            
        except Exception as e:
            logger.error("Submit command failed", error=str(e), exc_info=True)
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    async def cmd_config(self, args) -> int:
        """
        View or validate configuration.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code
        """
        try:
            if args.validate:
                # Validate configuration
                loader = get_config_loader()
                config = loader.load()
                print("Configuration is valid")
                print(f"Base directory: {config.base_dir}")
                return 0
            
            if args.show or not any([args.validate]):
                # Show configuration
                config = get_config(args.path)
                print("=== Agentic OS Configuration ===")
                print(f"Base directory: {config.base_dir}")
                print(f"\nPlanner:")
                print(f"  Model: {config.planner.model_name}")
                print(f"  Critic model: {config.planner.critic_model}")
                print(f"  Ollama host: {config.planner.ollama_host}")
                print(f"\nMemory:")
                print(f"  Working size: {config.memory.working_memory_size}")
                print(f"  Episodic DB: {config.memory.episodic_db_path}")
                print(f"  Semantic DB: {config.memory.semantic_db_path}")
                print(f"\nScheduler:")
                print(f"  Workers: {config.scheduler.worker_count}")
                print(f"  Cgroup path: {config.scheduler.cgroup_path}")
                print(f"\nLogging:")
                print(f"  Level: {config.logging.level}")
                print(f"  Format: {config.logging.format}")
                print(f"  Log dir: {config.logging.log_dir}")
            
            return 0
            
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    async def cmd_logs(self, args) -> int:
        """
        View system logs.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code
        """
        try:
            config = get_config()
            log_file = Path(config.logging.log_dir) / "agentic-os.log"
            
            if not log_file.exists():
                print(f"Log file not found: {log_file}", file=sys.stderr)
                return 1
            
            # Read and display log lines
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Filter by component if specified
            if args.component:
                lines = [l for l in lines if args.component in l]
            
            # Show tail
            tail_lines = lines[-args.tail:]
            print(''.join(tail_lines))
            
            if args.follow:
                print("\nFollowing logs (Ctrl+C to stop)...")
                # TODO: Implement log following in future phases
                print("Note: Log following not implemented in Phase 1")
            
            return 0
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    async def cmd_version(self, args) -> int:
        """
        Show version information.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code
        """
        print("Agentic OS v0.1.0 (Phase 1 - Foundation)")
        print("Python 3.11+")
        return 0
    
    async def run(self, args) -> int:
        """
        Run the CLI with parsed arguments.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code
        """
        if args.command == "status":
            return await self.cmd_status(args)
        elif args.command == "submit":
            return await self.cmd_submit(args)
        elif args.command == "config":
            return await self.cmd_config(args)
        elif args.command == "logs":
            return await self.cmd_logs(args)
        elif args.command == "version":
            return await self.cmd_version(args)
        else:
            self.parser.print_help()
            return 0


def main() -> int:
    """
    Main entry point for CLI.
    
    Returns:
        Exit code
    """
    cli = CLI()
    args = cli.parser.parse_args()
    
    if not args.command:
        cli.parser.print_help()
        return 0
    
    return asyncio.run(cli.run(args))


if __name__ == "__main__":
    sys.exit(main())
