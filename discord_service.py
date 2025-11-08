import discord
from discord.ext import commands
from datetime import datetime
from typing import List, Dict, Optional
import asyncio
import logging


class DiscordService:
    def __init__(self, token: str, channel_id: int):
        self.token = token
        self.channel_id = channel_id
        self.bot = None
        self.channel = None
        self.is_ready = False
        self.logger = logging.getLogger("AuroraMonitor.Discord")
        
        # Reference to monitor service (will be set externally)
        self.monitor_service = None
        
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        
        # Setup events
        @self.bot.event
        async def on_ready():
            self.logger.info(f'Discord bot logged in as {self.bot.user}')
            self.channel = self.bot.get_channel(self.channel_id)
            if not self.channel:
                self.logger.warning(f"Channel {self.channel_id} not found")
            else:
                self.logger.info(f"Connected to channel: {self.channel.name}")
            self.is_ready = True
        
        # Add commands
        @self.bot.command(name='status')
        async def status(ctx):
            """Check bot status"""
            await ctx.send("✅ Aurora Monitor is online and monitoring targets!")
        
        @self.bot.command(name='ping')
        async def ping_cmd(ctx):
            """Check bot latency"""
            latency = round(self.bot.latency * 1000, 2)
            await ctx.send(f"🏓 Pong! Latency: {latency}ms")
        
        @self.bot.command(name='ms')
        async def latency_stats(ctx):
            """Show latency statistics for all monitored targets"""
            if not self.monitor_service:
                await ctx.send("❌ Monitor service not available")
                return
            
            # Get statistics from monitor service
            stats = self.monitor_service.get_latency_statistics()
            
            if not stats['targets']:
                await ctx.send("📊 Nenhum destino está sendo monitorado")
                return
            
            # Create embed with statistics
            embed = discord.Embed(
                title="📊 Estatísticas de Latência",
                description=f"Latência e média dos últimos 300 segundos (5 min)",
                color=0x00BFFF,
                timestamp=datetime.utcnow()
            )
            
            # Add all targets
            targets_text = []
            for target_info in stats['targets']:
                status_icon = "🟢" if target_info['status'] == 'online' else "🔴"
                if target_info['status'] == 'online':
                    targets_text.append(
                        f"{status_icon} **{target_info['target']}**\n"
                        f"├ Atual: `{target_info['current_ms']:.2f}ms`\n"
                        f"├ Média (5min): `{target_info['avg_ms']:.2f}ms`\n"
                        f"├ Mínima (5min): `{target_info['min_ms']:.2f}ms`\n"
                        f"└ Máxima (5min): `{target_info['max_ms']:.2f}ms`"
                    )
                else:
                    targets_text.append(f"{status_icon} **{target_info['target']}** - SEM CONEXÃO")
            
            embed.add_field(
                name=f"🌐 Destinos ({len(stats['targets'])})",
                value="\n\n".join(targets_text) if targets_text else "Nenhum destino",
                inline=False
            )
            
            # Add summary
            online_count = stats['online_count']
            total_count = stats['total_count']
            uptime_percentage = (online_count / total_count * 100) if total_count > 0 else 0
            
            embed.add_field(
                name="📈 Resumo (Últimos 5 minutos)",
                value=f"**Online:** {online_count}/{total_count} ({uptime_percentage:.1f}%)",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    async def start_bot(self):
        """Start the Discord bot"""
        try:
            await self.bot.start(self.token)
        except Exception as e:
            self.logger.error(f"Failed to start Discord bot: {e}")
    
    async def wait_until_ready(self):
        """Wait until bot is ready"""
        while not self.is_ready:
            await asyncio.sleep(0.1)
    
    async def close(self):
        """Close Discord bot connection"""
        if self.bot:
            self.logger.info("Closing Discord bot connection...")
            await self.bot.close()
    
    async def send_alert(
        self, 
        title: str, 
        description: str, 
        color: int, 
        fields: Optional[List[Dict]] = None
    ):
        """Send alert to Discord channel"""
        if not self.channel:
            self.logger.warning("Discord channel not available")
            return
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', ''),
                    value=field.get('value', ''),
                    inline=field.get('inline', False)
                )
        
        try:
            await self.channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to send Discord message: {e}")
    
    async def send_startup_alert(self, target_count: int, interval: int):
        """Send startup notification"""
        await self.send_alert(
            title="🚀 Monitor Iniciado",
            description="Monitoramento de conectividade iniciado",
            color=0x00BFFF,  # Blue
            fields=[
                {'name': 'Alvos Monitorados', 'value': str(target_count), 'inline': True},
                {'name': 'Intervalo', 'value': f"{interval}s", 'inline': True}
            ]
        )
    
    async def send_target_down_alert(
        self, 
        target: str, 
        target_type: str, 
        failed_attempts: int
    ):
        """Send alert when target becomes unreachable"""
        await self.send_alert(
            title=f"⚠️ Conexão Perdida",
            description=f"Não foi possível conectar com **{target}**",
            color=0xFFFF99,  # Light yellow
            fields=[
                {'name': 'Destino', 'value': target, 'inline': True},
                {'name': 'Tipo', 'value': target_type, 'inline': True},
                {'name': 'Tentativas Falhas', 'value': str(failed_attempts), 'inline': True}
            ]
        )
    
    async def send_target_recovered_alert(
        self, 
        target: str, 
        target_type: str, 
        latency: float
    ):
        """Send alert when target recovers"""
        await self.send_alert(
            title=f"✅ Conexão Restaurada",
            description=f"Conexão com **{target}** foi restabelecida",
            color=0x00FF00,  # Green
            fields=[
                {'name': 'Destino', 'value': target, 'inline': True},
                {'name': 'Tipo', 'value': target_type, 'inline': True},
                {'name': 'Latência', 'value': f"{latency:.2f}ms", 'inline': True}
            ]
        )
    
    async def send_anomaly_alert(
        self, 
        target: str, 
        target_type: str, 
        current_latency: float, 
        avg_latency: float, 
        consecutive_count: int
    ):
        """Send alert for latency anomaly"""
        await self.send_alert(
            title=f"⚠️ Latência Anormal Detectada",
            description=f"Alta latência na conexão com **{target}**",
            color=0xFFA500,  # Orange
            fields=[
                {'name': 'Destino', 'value': target, 'inline': True},
                {'name': 'Tipo', 'value': target_type, 'inline': True},
                {'name': 'Latência Atual', 'value': f"{current_latency:.2f}ms", 'inline': True},
                {'name': 'Latência Média', 'value': f"{avg_latency:.2f}ms", 'inline': True},
                {'name': 'Anomalias Consecutivas', 'value': str(consecutive_count), 'inline': True}
            ]
        )
    
    async def send_critical_alert(
        self, 
        failed_count: int, 
        total_count: int, 
        failure_rate: float
    ):
        """Send critical alert when multiple targets are down"""
        await self.send_alert(
            title=f"🚨 CRÍTICO: Múltiplas Conexões Perdidas",
            description=f"**{failure_rate:.1f}%** das conexões monitoradas estão indisponíveis!",
            color=0xFF0000,  # Red
            fields=[
                {'name': 'Conexões Perdidas', 'value': str(failed_count), 'inline': True},
                {'name': 'Total Monitorado', 'value': str(total_count), 'inline': True},
                {'name': 'Taxa de Falha', 'value': f"{failure_rate:.1f}%", 'inline': True}
            ]
        )
