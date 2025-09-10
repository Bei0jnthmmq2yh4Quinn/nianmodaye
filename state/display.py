#!/usr/bin/env python3

"""
Status Display Engine for Monitor Package

This module provides unified rendering for all status display needs.
It replaces the scattered display logic throughout the system.
"""

from typing import List

from config import get_config
from config.schemas import DisplayContextConfig
from tools.logger import get_logger

from .enums import AlertLevel, DisplayMode, StatusContext
from .models import SystemStatus

logger = get_logger("state")


def get_display_config(context: StatusContext, mode: DisplayMode, **overrides) -> DisplayContextConfig:
    """Get display configuration from unified config system"""
    try:
        config = get_config()
        context_configs = config.display.contexts.get(context.value, {})
        mode_config = context_configs.get(mode.value)

        if mode_config:
            # Apply overrides to existing config
            if overrides:
                # Create a copy with overrides
                config_dict = {
                    "title": overrides.get("title", mode_config.title),
                    "show_workers": overrides.get("show_workers", mode_config.show_workers),
                    "show_alerts": overrides.get("show_alerts", mode_config.show_alerts),
                    "show_performance": overrides.get("show_performance", mode_config.show_performance),
                    "show_newline_prefix": overrides.get("show_newline_prefix", mode_config.show_newline_prefix),
                    "width": overrides.get("width", mode_config.width),
                    "max_alerts_per_level": overrides.get("max_alerts_per_level", mode_config.max_alerts_per_level),
                }
                return DisplayContextConfig(**config_dict)
            else:
                return mode_config
        else:
            # Create default config
            return _get_default_config(context, mode, **overrides)

    except Exception as e:
        logger.debug(f"Config load failed, using defaults: {e}")
        return _get_default_config(context, mode, **overrides)


def _get_default_config(context: StatusContext, mode: DisplayMode, **overrides) -> DisplayContextConfig:
    """Get default configuration values"""
    titles = {
        StatusContext.SYSTEM: "System Status",
        StatusContext.TASK_MANAGER: "Task Manager Status",
        StatusContext.MONITORING: "Pipeline Monitoring",
        StatusContext.APPLICATION: "Application Status",
        StatusContext.MAIN: "Pipeline Status",
    }

    defaults = {
        "title": titles.get(context, "Status"),
        "show_workers": mode not in [DisplayMode.COMPACT, DisplayMode.SUMMARY],
        "show_alerts": mode in [DisplayMode.DETAILED, DisplayMode.MONITORING],
        "show_performance": mode in [DisplayMode.DETAILED, DisplayMode.MONITORING],
        "show_newline_prefix": mode in [DisplayMode.DETAILED, DisplayMode.MONITORING],
        "width": 80,
        "max_alerts_per_level": 3,
    }

    # Apply overrides
    final_config = {**defaults, **overrides}
    return DisplayContextConfig(**final_config)


class StatusDisplayEngine:
    """
    Unified display engine that renders SystemStatus in various formats.
    Replaces all scattered display logic.
    """

    def render(
        self, status: SystemStatus, context: StatusContext, mode: DisplayMode, config: DisplayContextConfig
    ) -> None:
        """Main rendering entry point"""
        try:
            # Choose renderer based on mode
            if mode == DisplayMode.COMPACT:
                self._render_compact(status, config)
            elif mode == DisplayMode.SUMMARY:
                self._render_summary(status, config)
            elif mode == DisplayMode.MONITORING:
                self._render_monitoring(status, config)
            elif mode == DisplayMode.DETAILED:
                self._render_detailed(status, context, mode, config)
            else:  # STANDARD
                self._render_standard(status, config)

        except Exception as e:
            logger.error(f"Display rendering failed: {e}")
            self._render_fallback(status)

    def _render_compact(self, status: SystemStatus, config: DisplayContextConfig) -> None:
        """Render compact single-line format"""
        lines: List[str] = []

        # Compact header
        width = config.width
        lines.append("=" * width)
        lines.append(f"{config.title:^{width}}")
        lines.append("=" * width)

        # Compact pipeline info
        if status.has_pipeline_data():
            size = status.pipeline.queue_size()
            lines.append(f"Queues: {size} | Runtime: {status.runtime:.1f}s")

        # Compact provider info
        if status.has_provider_data():
            for name, provider in status.providers.items():
                abbrev = provider.abbreviations()  # Updated method name
                lines.append(
                    f"{name:>10} [{abbrev}]: "
                    f"valid={provider.resource.valid:>3}, "
                    f"links={provider.resource.links:>4}"
                )

        lines.append("=" * width)

        # Output
        for line in lines:
            logger.info(line)

    def _render_summary(self, status: SystemStatus, config: DisplayContextConfig) -> None:
        """Render brief summary format"""
        lines: List[str] = []

        # Summary header
        width = config.width
        lines.append("=" * width)
        lines.append(f"{config.title:^{width}}")
        lines.append("=" * width)

        # System summary
        lines.append(f"State: {status.state.value.title()} | Runtime: {status.runtime:.1f}s")

        if status.tasks.total > 0:
            lines.append(
                f"Tasks: {status.tasks.completed}/{status.tasks.total} " f"({status.tasks.success_rate:.1%} success)"
            )

        if status.resource.total > 0:
            lines.append(f"Keys: {status.resource.valid} valid, {status.resource.total} total")

        # Active providers summary - updated method name
        active_providers = status.active_providers()
        if active_providers:
            provider_names = [p.name for p in active_providers]
            lines.append(f"Active Providers: {', '.join(provider_names)}")

        lines.append("=" * width)

        # Output
        for line in lines:
            logger.info(line)

    def _render_standard(self, status: SystemStatus, config: DisplayContextConfig) -> None:
        """Render standard multi-line format"""
        lines: List[str] = []

        # Standard header
        width = config.width
        lines.append("=" * width)
        lines.append(f"{config.title:^{width}}")
        lines.append("=" * width)

        # Pipeline section
        if status.has_pipeline_data():
            lines.extend(self._format_pipeline_section(status, config))
            lines.append("-" * width)
        else:
            lines.append("No pipeline data available")
            lines.append("-" * width)

        # Provider section
        if status.has_provider_data():
            lines.extend(self._format_provider_section(status))
        else:
            lines.append("No provider data available")

        # Performance section
        if config.show_performance and status.performance.throughput > 0:
            lines.append("-" * width)
            lines.extend(self._format_performance_section(status))

        # Alerts section
        if config.show_alerts and status.has_alerts():
            lines.append("-" * width)
            lines.extend(self._format_alerts_section(status, config))

        lines.append("=" * width)

        # Output with compact formatting for stage tables
        for line in lines:
            if config.show_newline_prefix and line.startswith("="):
                logger.info("\n" + line)
            else:
                logger.info(line)

    def _render_monitoring(self, status: SystemStatus, config: DisplayContextConfig) -> None:
        """Render monitoring-specific format with performance data"""
        lines: List[str] = []

        # Monitoring header with performance summary
        width = config.width
        lines.append("=" * width)
        lines.append(f"{config.title:^{width}}")
        lines.append("=" * width)

        # Performance summary
        lines.append(
            f"Runtime: {status.runtime:.1f}s | "
            f"Throughput: {status.performance.throughput:.1f} tasks/sec | "
            f"Success: {status.performance.success_rate:.1%}"
        )

        if config.show_workers:
            lines.append(
                f"Workers: {status.worker.active}/{status.worker.total} active | "
                f"Queues: {status.pipeline.queue_size()} total"
            )

        lines.append("-" * width)

        # Detailed pipeline metrics
        if status.has_pipeline_data():
            lines.extend(self._format_pipeline_section(status, config))
            lines.append("-" * width)

        # Provider performance metrics
        if status.has_provider_data():
            lines.extend(self._format_provider_monitoring_section(status))

        # Always show alerts in monitoring mode
        if status.has_alerts():
            lines.append("-" * width)
            lines.extend(self._format_alerts_section(status, config))

        lines.append("=" * width)

        # Output
        for line in lines:
            logger.info(line)

    def _render_detailed(
        self, status: SystemStatus, context: StatusContext, mode: DisplayMode, config: DisplayContextConfig
    ) -> None:
        """Render detailed format with all information"""
        # Create detailed config with all sections enabled
        detailed_config = get_display_config(
            context,
            mode,
            title=config.title,
            show_workers=True,
            show_alerts=True,
            show_performance=True,
            show_newline_prefix=config.show_newline_prefix,
            width=config.width,
        )

        self._render_standard(status, detailed_config)

        # Add extra detailed sections
        lines: List[str] = []

        # System health section
        width = config.width
        lines.append("-" * width)
        lines.append("System Health:")
        lines.append(f"  Overall Status: {'Healthy' if status.healthy() else 'Issues Detected'}")
        lines.append(f"  Error Rate: {status.performance.error_rate:.1%}")
        lines.append(f"  Critical Alerts: {len(status.critical_alerts())}")

        # Resource utilization
        if status.worker.total > 0:
            lines.append(f"  Worker Utilization: {status.worker.utilization:.1%}")

        lines.append("=" * width)

        # Output additional sections
        for line in lines:
            logger.info(line)

    def _render_fallback(self, status: SystemStatus) -> None:
        """Render fallback display when main rendering fails"""
        width = 60  # Use fixed width for fallback
        lines: List[str] = [
            "=" * width,
            f"{'Status':^{width}}",
            "=" * width,
            f"System State: {status.state.value}",
            f"Runtime: {status.runtime:.1f} seconds",
            f"Providers: {len(status.providers)}",
            "=" * width,
        ]

        for line in lines:
            logger.info(line)

    def _format_pipeline_section(self, status: SystemStatus, config: DisplayContextConfig) -> List[str]:
        """Format pipeline section with table-like layout"""
        lines: List[str] = []

        if not status.pipeline.stages:
            lines.append("No pipeline data available")
            return lines

        # Table header
        if config.show_workers:
            lines.append(f"{'Stage':<10} | {'Queue':<8} | {'Processed':<10} | {'Errors':<8} | {'Workers':<8}")
            lines.append("-" * config.width)

        # Table rows
        for name, metrics in status.pipeline.stages.items():
            if not name or not metrics:
                logger.debug(f"Ignore inviliad stage metrics data, stage: {name}, metrics: {metrics}")
                continue

            queue_size = metrics.queue_size
            processed = metrics.total_processed
            errors = metrics.total_errors
            workers = metrics.workers

            if config.show_workers:
                lines.append(f"{name:<10} | {queue_size:<8} | {processed:<10} | {errors:<8} | {workers:<8}")
            else:
                lines.append(f"{name:>10}: queue={queue_size:<4}, processed={processed:<6}, errors={errors}")

        return lines

    def _format_provider_section(self, status: SystemStatus) -> List[str]:
        """Format provider section with table-like layout"""
        lines: List[str] = []

        if not status.providers:
            lines.append("No provider data available")
            return lines

        # Table header
        lines.append(
            f"{'Provider':<12} | {'Valid':<6} | {'No Quota':<9} | {'Wait':<6} | {'Invalid':<8} | {'Links':<6} | {'Mode':<10}"
        )
        lines.append("-" * 80)  # Fixed width for provider table

        # Table rows
        for name, provider in status.providers.items():
            abbrev = provider.abbreviations()
            lines.append(
                f"{name:<12} | {provider.resource.valid:<6} | "
                f"{provider.resource.no_quota:<9} | {provider.resource.wait_check:<6} | "
                f"{provider.resource.invalid:<8} | {provider.resource.links:<6} | "
                f"{abbrev:<10}"
            )

        return lines

    def _format_provider_monitoring_section(self, status: SystemStatus) -> List[str]:
        """Format provider section with monitoring metrics"""
        lines: List[str] = []

        for name, provider in status.providers.items():
            abbrev = provider.abbreviations()
            success_rate = provider.resource.success_rate * 100

            lines.append(
                f"{name:<12} [{abbrev:>8}] | "
                f"Valid: {provider.resource.valid:>4} | "
                f"Rate: {success_rate:>5.1f}% | "
                f"Links: {provider.resource.links:>5} | "
                f"API: {provider.success_rate:.1%}"
            )

        return lines

    def _format_performance_section(self, status: SystemStatus) -> List[str]:
        """Format performance metrics section"""
        lines: List[str] = [
            "Performance Metrics:",
            f"  Throughput: {status.performance.throughput:.2f} tasks/sec",
            f"  Success Rate: {status.performance.success_rate:.1%}",
            f"  Error Rate: {status.performance.error_rate:.1%}",
        ]

        if status.performance.avg_response_time > 0:
            lines.append(f"  Avg Response Time: {status.performance.avg_response_time:.2f}s")

        return lines

    def _format_alerts_section(self, status: SystemStatus, config: DisplayContextConfig) -> List[str]:
        """Format alerts section"""
        lines: List[str] = ["Alerts:"]

        # Group alerts by level
        critical_alerts = [a for a in status.alerts if a.level == AlertLevel.CRITICAL]
        error_alerts = [a for a in status.alerts if a.level == AlertLevel.ERROR]
        warning_alerts = [a for a in status.alerts if a.level == AlertLevel.WARNING]
        info_alerts = [a for a in status.alerts if a.level == AlertLevel.INFO]

        max_alerts = config.max_alerts_per_level
        max_info = max(1, max_alerts - 1)  # Info shows one less

        if critical_alerts:
            lines.append(f"  CRITICAL ({len(critical_alerts)}):")
            for alert in critical_alerts[:max_alerts]:
                lines.append(f"    - {alert.message}")

        if error_alerts:
            lines.append(f"  ERROR ({len(error_alerts)}):")
            for alert in error_alerts[:max_alerts]:
                lines.append(f"    - {alert.message}")

        if warning_alerts:
            lines.append(f"  WARNING ({len(warning_alerts)}):")
            for alert in warning_alerts[:max_alerts]:
                lines.append(f"    - {alert.message}")

        if info_alerts:  # Remove mode check, always show if available
            lines.append(f"  INFO ({len(info_alerts)}):")
            for alert in info_alerts[:max_info]:
                lines.append(f"    - {alert.message}")

        # If no alerts of any level, show a message
        if not (critical_alerts or error_alerts or warning_alerts or info_alerts):
            lines.append("  No alerts")

        return lines
