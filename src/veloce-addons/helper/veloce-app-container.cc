/*
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author: Douglas D. Agbeve <douglas.agbeve@uantwerpen.be>
 */

#include "veloce-app-container.h"

#include "ns3/log.h"
#include "ns3/names.h"

namespace ns3
{

NS_LOG_COMPONENT_DEFINE("VeloceAppContainer");

VeloceAppContainer::VeloceAppContainer()
{
}

VeloceAppContainer::VeloceAppContainer(Ptr<Application> app)
{
    m_applications.push_back(app);
}

VeloceAppContainer::Iterator
VeloceAppContainer::Begin() const
{
    return m_applications.begin();
}

VeloceAppContainer::Iterator
VeloceAppContainer::End() const
{
    return m_applications.end();
}

uint32_t
VeloceAppContainer::GetN() const
{
    return m_applications.size();
}

Ptr<Application>
VeloceAppContainer::Get(uint32_t i) const
{
    return m_applications[i];
}

void
VeloceAppContainer::Add(VeloceAppContainer other)
{
    for (Iterator i = other.Begin(); i != other.End(); i++)
    {
        m_applications.push_back(*i);
    }
}

void
VeloceAppContainer::Add(Ptr<Application> application)
{
    m_applications.push_back(application);
}

void
VeloceAppContainer::Start(Time start) const
{
    for (Iterator i = Begin(); i != End(); ++i)
    {
        Ptr<Application> app = *i;
        app->SetStartTime(start);
    }
}

void
VeloceAppContainer::StartWithJitter(Time start, Ptr<RandomVariableStream> rv) const
{
    for (Iterator i = Begin(); i != End(); ++i)
    {
        Ptr<Application> app = *i;
        double value = rv->GetValue();
        NS_LOG_DEBUG("Start application at time " << start.GetSeconds() + value << "s");
        app->SetStartTime(start + Seconds(value));
    }
}

void
VeloceAppContainer::Stop(Time stop) const
{
    for (Iterator i = Begin(); i != End(); ++i)
    {
        Ptr<Application> app = *i;
        app->SetStopTime(stop);
    }
}

} //ns3 namespace
